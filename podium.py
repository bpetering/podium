import sys
import os
import os.path
import shutil
import glob
import re
from datetime import date
from http.server import HTTPServer, SimpleHTTPRequestHandler

from jinja2 import Environment, FileSystemLoader

BASE=os.path.expanduser('~/podium')

PAGES_DIR='pages'
POSTS_DIR='posts'
TEMPLATES_DIR='templates'
STATIC_DIR='static'
BUILD_DIR='build'

def read_meta(template_path):
    ret = {}
    meta_path = template_path + '.meta'
    if not os.path.exists(meta_path):
        raise Exception("tried to read meta that doesn't exist, path: {}".format(meta_path))
    with open(meta_path, 'r') as f:
        meta = f.read()
    delim = None
    equals_idx = meta.find('=')
    semicolon_idx = meta.find(':')
    if semicolon_idx == -1 and equals_idx != -1:
        delim = '='
    if equals_idx == -1 and semicolon_idx != -1:
        delim = ':'
    if equals_idx != -1 and semicolon_idx != -1:
        if equals_idx < semicolon_idx:
            delim = '='
        else:
            delim = ':'
    if delim is None:
        delim = ':'
    meta_lines = meta.replace('\r', '').split('\n')
    for line in meta_lines: 
        if len(line) and delim in line:
            key, val = line.split(delim)
            key = key.lower()
            key = re.sub(r'^\s+', '', key)
            key = re.sub(r'\s+$', '', key)
            val = re.sub(r'^\s+', '', val)
            val = re.sub(r'\s+$', '', val)
            ret[key] = val
    return ret

def get_url_from_path(path):
    global BASE
    return path.replace(BASE, '').replace('build', '').replace('.jinja', '')

def get_date_from_path(post_path):
    return re.findall(r'\d{4}/\d{2}/\d{2}', post_path)[0].replace('/', '-')

def get_posts(reverse_order=True):
    global BASE, POSTS_DIR
    post_files = [f for f in glob.glob(os.path.join(BASE, POSTS_DIR, '**'), recursive=True) 
                    if f.endswith('.jinja')]
    posts_meta = {}
    for f in post_files:
        posts_meta[f] = read_meta(f)
    post_files.sort(reverse=reverse_order)
    posts = [{
        'path': f, 
        'meta': posts_meta[f],
        'url':  get_url_from_path(f),
        'date': get_date_from_path(f),
        'title': posts_meta[f].get('title', '')
    } for f in post_files]
    return posts

def copy_entries(src_dir, dst_dir):
    """Copy files, and copy directories recursively, from src_dir to dst_dir"""
    entries = os.listdir(src_dir)
    num_files = 0
    num_dirs = 0
    for f in entries:
        full = os.path.join(src_dir, f)
        if os.path.isfile(full):
            shutil.copy(full, os.path.join(dst_dir, f))
            num_files += 1
        elif os.path.isdir(full):
            shutil.copytree(full, os.path.join(dst_dir, f))
            num_dirs += 1
        else:
            print("- skipping copying {}, unsupported path type".format(full))
    print("+ copied {} files, and {} directories (recursively)".format(num_files, num_dirs))

def build():
    global BASE, PAGES_DIR, POSTS_DIR, TEMPLATES_DIR, STATIC_DIR, BUILD_DIR

    clean()

    # copy static/* dirs to build/
    print("+ Copying static...")
    copy_entries(os.path.join(BASE, STATIC_DIR), os.path.join(BASE, BUILD_DIR))

    # copy posts/* (files and dirs) to build/posts/
    print("+ Copying posts...")
    copy_entries(os.path.join(BASE, POSTS_DIR), os.path.join(BASE, BUILD_DIR, 'posts'))

    # copy pages/* (files and dirs) to build/
    print("+ Copying pages...")
    copy_entries(os.path.join(BASE, PAGES_DIR), os.path.join(BASE, BUILD_DIR))

    # find all jinja files in build and render 
    jinja_env = Environment(
        loader=FileSystemLoader(BASE)
    )
    old_cwd = os.getcwd()
    os.chdir(BASE)
    build_templates = [f for f in glob.glob('build/**', recursive=True) if f.endswith('.jinja')]
    for template_path in build_templates:
        template = jinja_env.get_template(template_path)
        context_dict = {}
        context_dict['today'] = date.today()
        context_dict['meta'] = read_meta(template_path)
        context_dict['title'] = context_dict['meta'].get('title', '')
        if 'posts' in template_path:
            context_dict['date'] = get_date_from_path(template_path)
        context_dict['posts'] = get_posts()
        context_dict['url'] = get_url_from_path(template_path)

        with open(template_path + '.ren', 'w') as f:
            f.write(template.render(context_dict))

        final_path = template_path.replace('.jinja', '')
        os.remove(template_path)
        os.rename(template_path + '.ren', final_path)
        print("++ Rendered {}{}".format(final_path, ' including meta' if context_dict['meta'] else ''))

    os.chdir(old_cwd)

def view():
    global BASE, BUILD_DIR
    build_dir = os.path.join(BASE, BUILD_DIR)
    if not os.path.exists(build_dir):
        build()
    old_cwd = os.getcwd()
    os.chdir(build_dir)
    print("+ Serving on http://127.0.0.1:8000/")
    httpd = HTTPServer(('127.0.0.1', 8000), SimpleHTTPRequestHandler)
    httpd.serve_forever()
    os.chdir(old_cwd)

def clean():
    global BASE, BUILD_DIR
    build_dir = os.path.join(BASE, BUILD_DIR)
    shutil.rmtree(build_dir, ignore_errors=True)
    print("+ Removed {}".format(build_dir))

def show_help():
    print('Usage: podium.py [--build/--view/--clean]')
    print('     build:      build site from templates (removes build directory contents)')
    print('     view:       start a local webserver and browser to view the site')
    print('     clean:      removes build directory')
    sys.exit(1)


def run(action):
    if action not in ('build', 'view', 'clean'):
        show_help()
            
    if action == 'build':
        build()

    if action == 'view':
        view()

    if action == 'clean':
        clean()

if __name__ == '__main__':
    for d in (PAGES_DIR, POSTS_DIR, STATIC_DIR, TEMPLATES_DIR):
        full = os.path.join(BASE, d)
        if not os.path.exists(full):
            os.mkdir(full)

    if len(sys.argv) < 2:
        show_help()
    run(sys.argv[1])

