import argparse
import aiofiles
import asyncio
import logging
import os
from aiohttp import web


CHUNK_SIZE = 1024 * 100


async def archivate(request):
    photos_path = request.app.args['path']
    archive_name = request.match_info['archive_hash']
    if os.path.exists(os.path.join(photos_path, archive_name)) is False:
        if request.app.args['logging']:
            logging.error(f'no archive with name: {archive_name}')
        raise web.HTTPNotFound(text='Такого архива нет',
                               content_type='text/html')
    response = web.StreamResponse()
    attachment = f'attachment; filename="{archive_name}.zip'
    response.headers['Content-Disposition'] = attachment
    await response.prepare(request)
    if request.app.args['logging']:
        logging.debug(f'send headers')
    process = await asyncio.create_subprocess_exec(
        'zip',
        *['-r', '-', archive_name],
        cwd=photos_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)
    try:
        while True:
            stdout = await process.stdout.read(CHUNK_SIZE)
            if request.app.args['logging']:
                logging.info('Sending archive chunk ...')
            await response.write(stdout)
            if request.app.args['low_speed']:
                await asyncio.sleep(2)
            if process.stdout.at_eof():
                if request.app.args['logging']:
                    logging.info('Send all')
                break
    except asyncio.CancelledError:
        if request.app.args['logging']:
            logging.error('Download was interrupted')
        process.kill()
        await process.communicate()
    finally:
        return response


async def handle_index_page(request):
    async with aiofiles.open('index.html',
                             mode='r',
                             encoding='utf-8') as index_file:
        index_contents = await index_file.read()
    return web.Response(text=index_contents,
                        content_type='text/html')


def get_args():
    parser = argparse.ArgumentParser(description='async photo server.')
    parser.add_argument('-log',
                        '--logging',
                        action='store_true',
                        help='logging mode on/off')
    parser.add_argument('-s',
                        '--low_speed',
                        action='store_true',
                        help='low speed mode on/off')
    parser.add_argument('-p',
                        '--path',
                        type=str,
                        help='path to photos on/off',
                        default="test_photos")
    args = parser.parse_args()
    return args


if __name__ == '__main__':
    app_args = get_args()
    logging.basicConfig(level=logging.INFO)

    app = web.Application()
    app.args = {
        'path': app_args.path,
        'low_speed': app_args.low_speed,
        'logging': app_args.logging
    }
    app.add_routes([
        web.get('/', handle_index_page),
        web.get('/archive/{archive_hash}/', archivate)
    ])
    web.run_app(app)
