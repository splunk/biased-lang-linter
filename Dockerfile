FROM lng88/biased_lang:v1.test

RUN ls
RUN cd ./pink-panther
ENTRYPOINT [ "python3", "run_json.py", "--mode=check", "--path=$GITHUB_WORKSPACE"]