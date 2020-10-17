import sys
import os
import os.path
import signal
import shutil
import glob
import re
import time
from datetime import date
from http.server import HTTPServer, SimpleHTTPRequestHandler

import inotify.adapters     # TODO non-linux
from jinja2 import Environment, FileSystemLoader

# TODO live reload browser with xdotool

BASE=os.path.expanduser('~/podium')

PAGES_DIR='pages'
POSTS_DIR='posts'
TEMPLATES_DIR='templates'
STATIC_DIR='static'
BUILD_DIR='build'
BUILD_TAGS_DIR='tags'

IGNORE_FILENAMES=('tags', 'tags.temp', 'tags.lock')
IGNORE_EXTS=('.swp', '.swx')

def read_meta(meta_path):
    ret = {}
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
            key, _, val = line.partition(delim)
            key = key.lower()
            key = re.sub(r'^\s+', '', key)
            key = re.sub(r'\s+$', '', key)
            val = re.sub(r'^\s+', '', val)
            val = re.sub(r'\s+$', '', val)
            if key == 'tags':
                ret[key] = [x.lower().strip() for x in val.split(',') if x != ',']
            else:
                ret[key] = val
    return ret

def url_friendly(s):
    return re.sub(r'\W', '', s)

def get_url_from_path(path):
    global BASE
    tmp = path.replace(BASE, '').replace('build' + os.sep, '').replace('.jinja', '')
    if not tmp.startswith('/'):
        tmp = '/' + tmp
    return tmp

def get_date_from_path(post_path):
    return date.fromisoformat(re.findall(r'\d{4}/\d{2}/\d{2}', post_path)[0].replace('/', '-'))

def format_date_html(date_obj):
    d = date_obj.strftime('%d')
    if d[-1] == '1':
        suffix = 'st'
    elif d[-1] == '2':
        suffix = 'nd'
    elif d[-1] == '3' and d != '13':
        suffix = 'rd'
    else:
        suffix = 'th'
    return '{}<sup>{}</sup> {}'.format(d, suffix, date_obj.strftime('%B %Y'))

def get_post_files():
    global BASE, POSTS_DIR
    post_files = [f for f in glob.glob(os.path.join(BASE, POSTS_DIR, '**'), recursive=True) 
                    if f.endswith('.jinja')]
    return post_files

def get_posts(reverse_order=True):
    posts_meta = {}
    post_files = get_post_files()
    for f in post_files:
        posts_meta[f] = read_meta(f + '.meta')
    # Alphabetic sort, that works first with dates, because of dir structure, second 
    # alphabetically within that date
    post_files.sort(reverse=reverse_order)
    posts = [{
        'path': f, 
        'meta': posts_meta[f],
        'url':  get_url_from_path(f),
        'date': format_date_html(get_date_from_path(f)),
        'title': posts_meta[f].get('title', ''),
        'tags': posts_meta[f].get('tags', '')
    } for f in post_files]
    return posts

def get_tags_with_posts():
    post_files = get_post_files()
    all_metas = [(x, read_meta(x + '.meta')) for x in post_files]    
    tags = {}
    for item in all_metas:
        file_path, meta = item
        if 'tags' not in meta:
            continue
        for meta_tag in meta['tags']:
            if meta_tag not in tags:
                tags[meta_tag] = {}
                tags[meta_tag]['name'] = meta_tag
                tags[meta_tag]['posts'] = []
                tags[meta_tag]['friendly'] = url_friendly(meta_tag)
            tags[meta_tag]['posts'].append({
                'date': format_date_html(get_date_from_path(file_path)), 
                'url':  get_url_from_path(file_path),
                'title': meta['title']
            })
    return tags

def copy_entries(src_dir, dst_dir, quiet=False):
    """Copy files, and copy directories recursively, from src_dir to dst_dir"""
    entries = os.listdir(src_dir)
    num_files = 0
    num_dirs = 0
    for f in entries:
        if f in IGNORE_FILENAMES:
            continue
        if f[f.rfind('.'):] in IGNORE_EXTS:
            continue
        if f.endswith('~'):
            continue
        full = os.path.join(src_dir, f)
        if os.path.isfile(full):
            shutil.copy(full, os.path.join(dst_dir, f))
            num_files += 1
        elif os.path.isdir(full):
            shutil.copytree(full, os.path.join(dst_dir, f))
            num_dirs += 1
        else:
            if not quiet:
                print("- skipping copying {}, unsupported path type".format(full))
    if not quiet:
        print("+ copied {} files, and {} directories (recursively)".format(num_files, num_dirs))

def build_compressed(archive_types=('zip', 'gztar')):
    # Rename directory so it's clearer when downloaded and unpacked
    build_path = os.path.join(BASE, BUILD_DIR)

    # Use /tmp to hide username from .tar archive meta
    arc_build_path = os.path.join('/tmp', SITE_META['name']) # TODO windows, TODO no site meta
    shutil.rmtree(arc_build_path, ignore_errors=True)
    shutil.copytree(build_path, arc_build_path)

    for archive_type in archive_types:
        arc_name = '{}_{}'.format(SITE_META['name'], date.today().isoformat())
        arc_path = os.path.join('/tmp', arc_name)
        shutil.make_archive(arc_path, archive_type, '/tmp', SITE_META['name'])   # TODO windows

        # Move archive to within build/ directory
        ext = archive_type
        if archive_type == 'gztar':
            ext = 'tar.gz'
        os.rename(arc_path + '.' + ext, os.path.join(build_path, arc_name + '.' + ext))

    shutil.rmtree(arc_build_path)

def template_render_and_rename(template_path, context_dict, quiet=False):
    jinja_env = Environment(
            loader=FileSystemLoader([BASE, os.path.join(BASE, TEMPLATES_DIR)])
    )
    template = jinja_env.get_template(template_path)

    # Ensure certain things are always in context dict
    if 'today' not in context_dict:
        context_dict['today'] = date.today()
    if 'url' not in context_dict:
        context_dict['url'] = get_url_from_path(template_path)

    with open(template_path + '.ren', 'w') as f:
        f.write(template.render(context_dict))

    final_path = template_path.replace('.jinja', '')
    os.remove(template_path)
    os.rename(template_path + '.ren', final_path)
    if not quiet:
        print("++ Rendered {}{}".format(final_path, ' including meta' if 'meta' in context_dict else ''))

def build_tag_pages(site_posts, site_tags_with_posts, quiet=False):
    # Individual tags pages
    tag_template_path = os.path.join('templates', 'tag.jinja')
    tags_dir = os.path.join(BUILD_DIR, BUILD_TAGS_DIR)
    os.mkdir(tags_dir)

    for tag in site_tags_with_posts: 
        specific_tag_template_path = os.path.join(tags_dir, '{}.html.jinja'.format(url_friendly(tag)))
        shutil.copy2(tag_template_path, specific_tag_template_path)
        context_dict = {
            'title': 'Posts with tag "' + tag + '"',
            'tag': tag,
            'friendly_tag': url_friendly(tag),
            'site': {
                'posts': site_posts,
                'tags': site_tags_with_posts
            }
        }
        template_render_and_rename(specific_tag_template_path, context_dict, quiet=quiet)

    # All posts by tag
    all_posts_template_path = os.path.join('templates', 'postsbytag.jinja')
    build_all_posts_template_path = os.path.join(BUILD_DIR, 'postsbytag.html.jinja')
    shutil.copy2(all_posts_template_path, build_all_posts_template_path)
    del context_dict['tag']
    context_dict['title'] = 'Posts by Tag'
    template_render_and_rename(build_all_posts_template_path, context_dict, quiet=quiet)

def build(quiet=False):
    clean(quiet=quiet)

    # Implications for URL structure:
    # - posts are by-date (3 directory levels) under /posts/<date>/name.html
    # - pages are /<pagename>.html, unless in a subdir in pages/

    # copy static/* dirs to build/
    if not quiet:
        print("+ Copying static...")
    copy_entries(os.path.join(BASE, STATIC_DIR), os.path.join(BASE, BUILD_DIR), quiet=quiet)

    # copy posts/* (files and dirs) to build/posts/
    if not quiet:
        print("+ Copying posts...")
    copy_entries(os.path.join(BASE, POSTS_DIR), os.path.join(BASE, BUILD_DIR, 'posts'), quiet=quiet)

    # copy pages/* (files and dirs) to build/
    if not quiet:
        print("+ Copying pages...")
    copy_entries(os.path.join(BASE, PAGES_DIR), os.path.join(BASE, BUILD_DIR), quiet=quiet)

    old_cwd = os.getcwd()
    os.chdir(BASE)
    build_templates = [f for f in 
                        glob.glob(os.path.join(BUILD_DIR, '**'), recursive=True) 
                        if f.endswith('.jinja')]
    # Run these expensive functions only once
    site_posts = get_posts()
    site_tags_with_posts = get_tags_with_posts()

    for template_path in build_templates:
        context_dict = read_meta(template_path + '.meta')
        url = get_url_from_path(template_path)
        context_dict['url'] = url
        context_dict['tags'] = [{
            'name': x,
            'friendly': url_friendly(x)
        } for x in context_dict.get('tags', [])]

        # Posts only
        if template_path.startswith(os.path.join(BUILD_DIR, 'posts', '')):
            context_dict['date'] = format_date_html(get_date_from_path(template_path))
            # Find prev and next posts
            tmpl_post_idx = [x['url'] for x in site_posts].index(url)
            if tmpl_post_idx < len(site_posts) - 1:
                context_dict['prev'] = {
                    'title': site_posts[tmpl_post_idx + 1]['title'],    # reverse sorted, +1 is earlier
                    'url':   site_posts[tmpl_post_idx + 1]['url']
                }
            if tmpl_post_idx > 0:
                context_dict['next'] = {
                    'title': site_posts[tmpl_post_idx - 1]['title'],
                    'url':   site_posts[tmpl_post_idx - 1]['url']
                }

        # Provide all posts in site and all tags in site via .site
        context_dict['site'] = {}
        context_dict['site']['posts'] = site_posts
        context_dict['site']['tags'] = site_tags_with_posts

        template_render_and_rename(template_path, context_dict, quiet=quiet)

    build_tag_pages(site_posts, site_tags_with_posts, quiet=quiet)
    build_compressed(('zip', 'gztar'))

    os.chdir(old_cwd)

def watch():
    global BASE, BUILD_DIR
    build_dir = os.path.join(BASE, BUILD_DIR)
    
    while True:
        build(quiet=True)
        print("+ rebuilt")

        # Fork, and start a web server in the child, and a filesystem watcher in the parent.
        # If the site is modified, stop webserver, rebuild, and restart the webserver (it doesn't 
        # like it when its cwd goes away)
        ret = os.fork()
        if ret == 0:
            # Child
            os.chdir(build_dir)
            httpd = HTTPServer(('127.0.0.1', 8000), SimpleHTTPRequestHandler)
            httpd.serve_forever()
        else:
            # Parent
            print("+ Serving on http://127.0.0.1:8000/, Ctrl-C to stop\n")
            i = inotify.adapters.InotifyTree(BASE)
            for event in i.event_gen():
                # We're only interested in create, delete, move, write events (not dir list)
                # (and ignore tags files)
                if event is None:
                    continue
                (_, type_names, path, filename) = event
                if filename in IGNORE_FILENAMES:
                    continue
                if '.' in filename:
                    if filename[filename.rfind('.'):] in IGNORE_EXTS: 
                        continue
                if filename.endswith('~'):
                    continue
                if 'IN_CLOSE_WRITE' in type_names or 'IN_DELETE' in type_names or 'IN_MOVED_TO' in type_names \
                or type_names == ['IN_CREATE', 'IN_ISDIR']:
                    os.kill(ret, signal.SIGKILL)
                    print("+ [{}/{}] changed, rebuilding...".format(path, filename))
                    time.sleep(1)
                    break

def clean(quiet=False):
    global BASE, BUILD_DIR
    build_dir = os.path.join(BASE, BUILD_DIR)
    shutil.rmtree(build_dir, ignore_errors=True)
    if not quiet:
        print("+ Removed {}".format(build_dir))

def show_help():
    print('Usage: podium.py [clean/build/watch]')
    print('     clean:      removes build directory (no build)')
    print('     build:      build site from templates')
    print('     watch:      start a local webserver and browser to view the site, rebuilding when there are changes')
    sys.exit(1)

def run(action):
    if action not in ('build', 'watch', 'clean'):
        show_help()
            
    if action == 'build':
        build()

    if action == 'watch':
        watch()

    if action == 'clean':
        clean()

if __name__ == '__main__':
    global SITE_META

    SITE_META = read_meta(os.path.join(BASE, 'site.meta'))
    
    if not os.path.exists(BASE):
        os.mkdir(BASE)

    for d in (PAGES_DIR, POSTS_DIR, STATIC_DIR, TEMPLATES_DIR):
        full = os.path.join(BASE, d)
        if not os.path.exists(full):
            os.mkdir(full)

    if len(sys.argv) < 2:
        show_help()
    run(sys.argv[1])

