FROM lng88/biased_lang:v1.test

RUN ls
RUN pwd
COPY entrypoint.sh /entrypoint.sh

# ENTRYPOINT [ "python3", "/pink-panther/run_json.py"]
ENTRYPOINT ["/entrypoint.sh"]