from flask import Flask, request
from ocdskingfisherprocess.config import Config, ROOT
from ocdskingfisherprocess.store import Store
from ocdskingfisherprocess.database import DataBase
import tempfile
import datetime
import os

config = Config()
config.load_user_config()

app = Flask(__name__)


@app.route("/")
def hello():
    return "OCDS Kingfisher"


@app.route("/robots.txt")
def robots_txt():
    return "User-agent: *\nDisallow: /"


@app.route("/api/")
def api():
    return "OCDS Kingfisher APIs"


@app.route("/api/v1/")
def api_v1():
    return "OCDS Kingfisher APIs V1 **DEBUGGING**"


@app.route("/api/v1/submit/file/", methods=['POST'])
def api_v1_submit_file():
    app.logger.info(request)
    # TODO this allows GET API_KEY values only, allow POST and header too!
    api_key = request.args.get('API_KEY')
    if not api_key or api_key not in config.web_api_keys:
        return "ACCESS DENIED"  # TODO proper error

    # TODO check all required fields are there!
    logpath = os.path.join(ROOT, "requestlogsasdf", datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")+".log")
    try:
        with open(logpath, "w+") as logfile:
            logfile.write(request.form)
            logfile.write(request.form.get('collection_source'))
            logfile.write(request.files['file'])
            logfile.write("asdf!")
            logfile.write(request.method)
            logfile.write(request.args.get('API_KEY'))
    except:
        print(request.form.to_dict())
        print(request.args.get('API_KEY'))
        print(request.method)

    # database = DataBase(config=config)
    # store = Store(config=config, database=database)

    # store.load_collection(
    #     request.form.get('collection_source'),
    #     request.form.get('collection_data_version'),
    #     True if request.form.get('collection_sample', '0') in ['1'] else False,
    # )

    # (tmp_file, tmp_filename) = tempfile.mkstemp(prefix="ocdskf-")
    # os.close(tmp_file)

    # request.files['file'].save(tmp_filename)

    # store.store_file_from_local(
    #     request.form.get('file_name'),
    #     request.form.get('file_url'),
    #     request.form.get('file_data_type'),
    #     request.form.get('file_encoding'),
    #     tmp_filename
    # )

    # os.remove(tmp_filename)

    return "OCDS Kingfisher APIs V1 Submit"


@app.route("/api/v1/submit/item/", methods=['POST'])
def api_v1_submit_item():
    app.logger.info(request)
    # TODO this allows GET API_KEY values only, allow POST and header too!
    api_key = request.args.get('API_KEY')
    if not api_key or api_key not in config.web_api_keys:
        return "ACCESS DENIED"  # TODO proper error

    # TODO check all required fields are there!

    database = DataBase(config=config)
    store = Store(config=config, database=database)

    store.load_collection(
        request.form.get('collection_source'),
        request.form.get('collection_data_version'),
        True if request.form.get('collection_sample', '0') in ['1'] else False,
    )

    (tmp_file, tmp_filename) = tempfile.mkstemp(prefix="ocdskf-")
    os.close(tmp_file)

    request.files['file'].save(tmp_filename)

    store.store_file_item_from_local(
        request.form.get('file_name'),
        request.form.get('file_url'),
        request.form.get('file_data_type'),
        request.form.get('file_encoding'),
        int(request.form.get('number')),
        tmp_filename
    )

    os.remove(tmp_filename)

    return "OCDS Kingfisher APIs V1 Submit"
