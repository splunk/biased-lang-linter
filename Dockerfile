FROM lng88/biased_lang:v1.test

WORKDIR /pink-panther
RUN ls
RUN pwd
ENTRYPOINT [ "python3", "run_json.py", "--mode=check", "--path=${GITHUB_WORKSPACE}"]