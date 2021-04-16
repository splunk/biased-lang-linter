FROM lng88/biased_lang:v1.test

WORKDIR /pink-panther

ENTRYPOINT [ "python", "run_json.py" ]