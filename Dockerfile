FROM lng88/biased_lang:v1.test

RUN ls
RUN pwd
RUN echo $GITHUB_WORKSPACE

ENTRYPOINT [ "python3", "/pink-panther/run_json.py", "--mode=check", "--path=$GITHUB_WORKSPACE"]