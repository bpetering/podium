function postvim {
    filename=$1
    if [ -z $filename ]; then
        echo "filename (with or without .html.jinja extension): "
        read filename
    fi
    filename=$(echo $filename | sed -e 's/.jinja//' | sed -e 's/.html//')
    dirpath=~/soapbox/posts/$(date +%Y)/$(date +%m)/$(date +%d)
    filepath=$dirpath/$filename.html.jinja
    mkdir -p $dirpath && echo -e "{% extends 'post.jinja' %}\n\n{% block content %}\n{{ super() }}\n\n{% endblock content %}\n\n" > $filepath
    echo 'Title: ' > $filepath.meta
    vim $filepath $filepath.meta
}

