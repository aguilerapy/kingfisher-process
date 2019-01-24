from ocdskingfisherprocess.util import parse_string_to_date_time, FileToStore
import os


def test_parse_string_to_date_time_1():
    date = parse_string_to_date_time("2019-04-01 10:11:12")
    assert "2019-04-01 10-11-12" == date.strftime("%Y-%m-%d %H-%M-%S")


def test_parse_string_to_date_time_2():
    date = parse_string_to_date_time("2019-04-01-10-11-12")
    assert "2019-04-01 10-11-12" == date.strftime("%Y-%m-%d %H-%M-%S")


def test_file_to_store_sample_1_0_record_with_control_codes():
    json_filename = os.path.join(os.path.dirname(
        os.path.realpath(__file__)), 'data', 'sample_1_0_record_with_control_codes.json'
    )

    with FileToStore(json_filename) as file_to_store:
        # Processing is required in this file, so path should be different
        assert file_to_store.get_filename() != json_filename

        assert len(file_to_store.get_warnings()) == 1
        assert file_to_store.get_warnings()[0] == 'We had to replace control codes: chr(16)'


def test_file_to_store_sample_1_0_record():
    json_filename = os.path.join(os.path.dirname(
        os.path.realpath(__file__)), 'data', 'sample_1_0_record.json'
    )

    with FileToStore(json_filename) as file_to_store:
        # Processing is NOT required in this file, so path should be same
        assert file_to_store.get_filename() == json_filename

        assert len(file_to_store.get_warnings()) == 0
