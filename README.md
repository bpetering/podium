# podium

An opinionated, useful static-site generator in Python. A less minimalistic, fuller-featured version of [soapbox](https://github.com/bpetering/soapbox), that is backward-compatible (you can start using `podium` with a `soapbox` site and continue from there - now it's a `podium` site).

## Overview

Features:
* generates an entire site from templates
* `build` action, to rebuild the site, `watch`, to view site in local browser (with live-reload)
* tags and categories
* automatic sitemap generation
* generates archive of site to download
* library of macros

## Do I use this or [soapbox](https://github.com/bpetering/soapbox)?

Probably this (`podium`). Soapbox is good if you *just need to get started*, and want something that 
(almost entirely) gets out of your way. Podium is good when you start to think "I like the minimalism, but..."

## Usage

### Installation

```
git clone https://github.com/bpetering/podium
cd podium
python -m venv venvpodium
source venvpodium/bin/activate
pip install -r requirements.txt
```

### Building a site

If you're starting with a site built with `soapbox`, `mv ~/soapbox/* ~/podium/`.

`python podium.py build` to build your site from templates

`python podium.py clean` to remove the build

`python podium.py watch` to start a web server, rebuilding if site changes, with live-reload

Once you're happy, copy the `~/podium/build` directory contents to your domain's docroot (e.g. `rsync -v -a -e 'ssh' build/ you@yourserver:/var/www/example.org/`)

