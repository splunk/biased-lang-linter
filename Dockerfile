FROM lng88/biased_lang:v1.test

WORKDIR $GITHUB_WORKSPACE
RUN ls
RUN pwd
ENTRYPOINT [ "python3", "run_json.py", "--mode=check", "--path=$GITHUB_WORKSPACE"]