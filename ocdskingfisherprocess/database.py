import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
import datetime
import json
import os
from functools import partial
import collections
from ocdskingfisherprocess.models import CollectionModel, FileModel, FileItemModel
import alembic.config
from ocdskingfisherprocess.util import get_hash_md5_for_data


class SetEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set):
            return list(obj)
        return json.JSONEncoder.default(self, obj)


class DataBase:

    def __init__(self, config):
        self.config = config
        self._engine = None

        self.metadata = sa.MetaData()

        self.collection_table = sa.Table('collection', self.metadata,
                                         sa.Column('id', sa.Integer, primary_key=True),
                                         sa.Column('source_id', sa.Text, nullable=False),
                                         sa.Column('data_version', sa.DateTime(timezone=False), nullable=False),
                                         sa.Column('store_start_at', sa.DateTime(timezone=False), nullable=False),
                                         sa.Column('store_end_at', sa.DateTime(timezone=False), nullable=True),
                                         sa.Column('sample', sa.Boolean, nullable=False, default=False),
                                         sa.Column('check_data', sa.Boolean, nullable=False, default=False),
                                         sa.Column('check_older_data_with_schema_version_1_1', sa.Boolean, nullable=False, default=False),
                                         sa.Column('transform_from_collection_id', sa.Integer,
                                                   sa.ForeignKey("collection.id"), nullable=True),
                                         sa.Column('transform_type', sa.Text, nullable=True),
                                         sa.UniqueConstraint('source_id', 'data_version', 'sample',
                                                             'transform_from_collection_id', 'transform_type',
                                                             name='unique_collection_identifiers'),
                                         )

        self.collection_file_table = sa.Table('collection_file', self.metadata,
                                              sa.Column('id', sa.Integer, primary_key=True),
                                              sa.Column('collection_id', sa.Integer,
                                                        sa.ForeignKey("collection.id",
                                                                      name="fk_collection_file_collection_id"),
                                                        nullable=False),
                                              sa.Column('filename', sa.Text, nullable=True),
                                              sa.Column('url', sa.Text, nullable=True),
                                              sa.Column('store_start_at', sa.DateTime(timezone=False),
                                                        nullable=True),
                                              sa.Column('store_end_at', sa.DateTime(timezone=False),
                                                        nullable=True),
                                              sa.Column('warnings', JSONB, nullable=True),
                                              sa.Column('errors', JSONB, nullable=True),
                                              sa.UniqueConstraint('collection_id', 'filename',
                                                                  name='unique_collection_file_identifiers'),
                                              )

        self.collection_file_item_table = sa.Table('collection_file_item', self.metadata,
                                                   sa.Column('id', sa.Integer, primary_key=True),
                                                   sa.Column('collection_file_id', sa.Integer,
                                                             sa.ForeignKey("collection_file.id",
                                                                           name="fk_collection_file_item_collection_file_id"),
                                                             nullable=False),
                                                   sa.Column('store_start_at', sa.DateTime(timezone=False),
                                                             nullable=True),
                                                   sa.Column('store_end_at', sa.DateTime(timezone=False),
                                                             nullable=True),
                                                   sa.Column('number', sa.Integer),
                                                   sa.UniqueConstraint('collection_file_id', 'number',
                                                                       name='unique_collection_file_item_identifiers'),
                                                   )

        self.data_table = sa.Table('data', self.metadata,
                                   sa.Column('id', sa.Integer, primary_key=True),
                                   sa.Column('hash_md5', sa.Text, nullable=False),
                                   sa.Column('data', JSONB, nullable=False),
                                   sa.UniqueConstraint('hash_md5', name='unique_data_hash_md5'),
                                   )

        self.package_data_table = sa.Table('package_data', self.metadata,
                                           sa.Column('id', sa.Integer, primary_key=True),
                                           sa.Column('hash_md5', sa.Text, nullable=False),
                                           sa.Column('data', JSONB, nullable=False),
                                           sa.UniqueConstraint('hash_md5', name='unique_package_data_hash_md5'),
                                           )

        self.release_table = sa.Table('release', self.metadata,
                                      sa.Column('id', sa.Integer, primary_key=True),
                                      sa.Column('collection_file_item_id', sa.Integer,
                                                sa.ForeignKey("collection_file_item.id",
                                                              name="fk_release_collection_file_item_id"),
                                                nullable=False),
                                      sa.Column('release_id', sa.Text, nullable=True),
                                      sa.Column('ocid', sa.Text, nullable=True),
                                      sa.Column('data_id', sa.Integer,
                                                sa.ForeignKey("data.id", name="fk_release_data_id"), nullable=False),
                                      sa.Column('package_data_id', sa.Integer,
                                                sa.ForeignKey("package_data.id", name="fk_release_package_data_id"),
                                                nullable=False),
                                      )

        self.record_table = sa.Table('record', self.metadata,
                                     sa.Column('id', sa.Integer, primary_key=True),
                                     sa.Column('collection_file_item_id', sa.Integer,
                                               sa.ForeignKey("collection_file_item.id",
                                                             name="fk_record_collection_file_item_id"), nullable=False),
                                     sa.Column('ocid', sa.Text, nullable=True),
                                     sa.Column('data_id', sa.Integer,
                                               sa.ForeignKey("data.id", name="fk_record_data_id"), nullable=False),
                                     sa.Column('package_data_id', sa.Integer,
                                               sa.ForeignKey("package_data.id", name="fk_record_package_data_id"),
                                               nullable=False),
                                     )

        self.compiled_release_table = sa.Table('compiled_release', self.metadata,
                                               sa.Column('id', sa.Integer, primary_key=True),
                                               sa.Column('collection_file_item_id', sa.Integer,
                                                         sa.ForeignKey("collection_file_item.id",
                                                                       name="fk_complied_release_collection_file_item_id"),
                                                         nullable=False),
                                               sa.Column('ocid', sa.Text, nullable=True),
                                               sa.Column('data_id', sa.Integer,
                                                         sa.ForeignKey("data.id", name="fk_complied_release_data_id"),
                                                         nullable=False),
                                               )

        self.release_check_table = sa.Table('release_check', self.metadata,
                                            sa.Column('id', sa.Integer, primary_key=True),
                                            sa.Column('release_id', sa.Integer,
                                                      sa.ForeignKey("release.id", name="fk_release_check_release_id"),
                                                      nullable=False),
                                            sa.Column('override_schema_version', sa.Text, nullable=True),
                                            sa.Column('cove_output', JSONB, nullable=False),
                                            sa.UniqueConstraint('release_id', 'override_schema_version',
                                                                name='unique_release_check_release_id_and_more')
                                            )

        self.record_check_table = sa.Table('record_check', self.metadata,
                                           sa.Column('id', sa.Integer, primary_key=True),
                                           sa.Column('record_id', sa.Integer,
                                                     sa.ForeignKey("record.id", name="fk_record_check_record_id"),
                                                     nullable=False),
                                           sa.Column('override_schema_version', sa.Text, nullable=True),
                                           sa.Column('cove_output', JSONB, nullable=False),
                                           sa.UniqueConstraint('record_id', 'override_schema_version',
                                                               name='unique_record_check_record_id_and_more')
                                           )

        self.release_check_error_table = sa.Table('release_check_error', self.metadata,
                                                  sa.Column('id', sa.Integer, primary_key=True),
                                                  sa.Column('release_id', sa.Integer, sa.ForeignKey("release.id",
                                                                                                    name="fk_release_check_error_release_id"),
                                                            nullable=False),
                                                  sa.Column('override_schema_version', sa.Text, nullable=True),
                                                  sa.Column('error', sa.Text, nullable=False),
                                                  sa.UniqueConstraint('release_id', 'override_schema_version',
                                                                      name='unique_release_check_error_release_id_and_more')
                                                  )

        self.record_check_error_table = sa.Table('record_check_error', self.metadata,
                                                 sa.Column('id', sa.Integer, primary_key=True),
                                                 sa.Column('record_id', sa.Integer, sa.ForeignKey("record.id",
                                                                                                  name="fk_record_check_error_record_id"),
                                                           nullable=False),
                                                 sa.Column('override_schema_version', sa.Text, nullable=True),
                                                 sa.Column('error', sa.Text, nullable=False),
                                                 sa.UniqueConstraint('record_id', 'override_schema_version',
                                                                     name='unique_record_check_error_record_id_and_more')
                                                 )

        self.transform_upgrade_1_0_to_1_1_status_release_table = sa.Table(
            'transform_upgrade_1_0_to_1_1_status_release',
            self.metadata,
            sa.Column(
                'source_release_id',
                sa.Integer,
                sa.ForeignKey(
                    "release.id",
                    name="fk_transform_upgrade_1_0_to_1_1_status_release_source_release_id"
                ),
                nullable=False,
                primary_key=True
            )
        )

        self.transform_upgrade_1_0_to_1_1_status_record_table = sa.Table(
            'transform_upgrade_1_0_to_1_1_status_record',
            self.metadata,
            sa.Column(
                'source_record_id',
                sa.Integer,
                sa.ForeignKey(
                    "record.id",
                    name="fk_transform_upgrade_1_0_to_1_1_status_record_source_record_id"
                ),
                nullable=False,
                primary_key=True
            )
        )

    def get_engine(self):
        # We only create a connection if actually needed; sometimes people do operations that don't need a database
        # and in that case no need to connect.
        # But this side of kingfisher now always requires a DB, so there should not be a problem opening a connection!
        if not self._engine:
            self._engine = sa.create_engine(
                self.config.database_uri,
                json_serializer=SetEncoder().encode,
                json_deserializer=partial(
                    json.loads,
                    object_pairs_hook=collections.OrderedDict),
            )
        return self._engine

    def delete_tables(self):
        engine = self.get_engine()
        engine.execute("drop table if exists transform_upgrade_1_0_to_1_1_status_record cascade")
        engine.execute("drop table if exists transform_upgrade_1_0_to_1_1_status_release cascade")
        engine.execute("drop table if exists record_check cascade")
        engine.execute("drop table if exists record_check_error cascade")
        engine.execute("drop table if exists release_check cascade")
        engine.execute("drop table if exists release_check_error cascade")
        engine.execute("drop table if exists record cascade")
        engine.execute("drop table if exists release cascade")
        engine.execute("drop table if exists compiled_release cascade")
        engine.execute("drop table if exists package_data cascade")
        engine.execute("drop table if exists data cascade")
        engine.execute("drop table if exists collection_file_item")
        engine.execute("drop table if exists collection_file_status cascade")  # This is the old table name
        engine.execute("drop table if exists collection_file cascade")
        engine.execute("drop table if exists source_session_file_status cascade")  # This is the old table name
        engine.execute("drop table if exists collection cascade")
        engine.execute("drop table if exists source_session cascade")  # This is the old table name
        engine.execute("drop table if exists alembic_version cascade")

    def create_tables(self):
        # Note this DOES NOT work with self.config!
        # It works with a brand new config instance that is created in ocdskingfisher/maindatabase/migrations/env.py
        # Not sure how to solve that
        alembicargs = [
            '--config', os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'mainalembic.ini')),
            '--raiseerr',
            'upgrade', 'head',
        ]
        alembic.config.main(argv=alembicargs)

    def get_collection_id(self, source_id, data_version, sample, transform_from_collection_id=None, transform_type=None):

        with self.get_engine().begin() as connection:
            s = sa.sql.select([self.collection_table]) \
                .where((self.collection_table.c.source_id == source_id) &
                       (self.collection_table.c.data_version == data_version) &
                       (self.collection_table.c.sample == sample) &
                       (self.collection_table.c.transform_from_collection_id == transform_from_collection_id) &
                       (self.collection_table.c.transform_type == transform_type))
            result = connection.execute(s)
            collection = result.fetchone()
            if collection:
                return collection['id']

    def get_or_create_collection_id(self, source_id, data_version, sample, transform_from_collection_id=None, transform_type=None):

        collection_id = self.get_collection_id(source_id, data_version, sample,
                                               transform_from_collection_id=transform_from_collection_id, transform_type=transform_type)
        if collection_id:
            return collection_id

        with self.get_engine().begin() as connection:
            value = connection.execute(self.collection_table.insert(), {
                'source_id': source_id,
                'data_version': data_version,
                'sample': sample,
                'transform_type': transform_type,
                'transform_from_collection_id': transform_from_collection_id,
                'store_start_at': datetime.datetime.utcnow(),
                'check_data': self.config.default_value_collection_check_data,
                'check_older_data_with_schema_version_1_1': self.config.default_value_collection_check_older_data_with_schema_version_1_1,
            })
            return value.inserted_primary_key[0]

    def get_all_collections(self):
        out = []
        with self.get_engine().begin() as connection:
            s = sa.sql.select([self.collection_table])
            for collection in connection.execute(s):
                out.append(CollectionModel(
                    database_id=collection['id'],
                    source_id=collection['source_id'],
                    data_version=collection['data_version'],
                    sample=collection['sample'],
                    transform_type=collection['transform_type'],
                    transform_from_collection_id=collection['transform_from_collection_id'],
                    check_data=collection['check_data'],
                    check_older_data_with_schema_version_1_1=collection['check_older_data_with_schema_version_1_1'],
                    store_start_at=collection['store_start_at'],
                    store_end_at=collection['store_end_at'],
                ))
        return out

    def get_collection(self, collection_id):
        with self.get_engine().begin() as connection:
            s = sa.sql.select([self.collection_table]) \
                .where(self.collection_table.c.id == collection_id)
            result = connection.execute(s)
            collection = result.fetchone()
            if collection:
                return CollectionModel(
                    database_id=collection['id'],
                    source_id=collection['source_id'],
                    data_version=collection['data_version'],
                    sample=collection['sample'],
                    transform_type=collection['transform_type'],
                    transform_from_collection_id=collection['transform_from_collection_id'],
                    check_data=collection['check_data'],
                    check_older_data_with_schema_version_1_1=collection['check_older_data_with_schema_version_1_1'],
                    store_start_at=collection['store_start_at'],
                    store_end_at=collection['store_end_at'],
                )

    def get_all_files_in_collection(self, collection_id):
        out = []
        with self.get_engine().begin() as connection:
            s = sa.sql.select([self.collection_file_table]) \
                .where(self.collection_file_table.c.collection_id == collection_id)
            for collection_file in connection.execute(s):
                out.append(FileModel(
                    database_id=collection_file['id'],
                    filename=collection_file['filename'],
                    url=collection_file['url'],
                    warnings=collection_file['warnings'],
                    errors=collection_file['errors'],
                    store_start_at=collection_file['store_start_at'],
                    store_end_at=collection_file['store_end_at'],
                ))
        return out

    def get_all_files_items_in_file(self, file):
        out = []
        with self.get_engine().begin() as connection:
            s = sa.sql.select([self.collection_file_item_table]) \
                .where(self.collection_file_item_table.c.collection_file_id == file.database_id)
            for result in connection.execute(s):
                out.append(FileItemModel(
                    database_id=result['id'],
                    number=result['number'],
                ))
        return out

    def is_release_check_done(self, release_id, override_schema_version=None):
        with self.get_engine().begin() as connection:
            s = sa.sql.select([self.release_check_table]) \
                .where((self.release_check_table.c.release_id == release_id) &
                       (self.release_check_table.c.override_schema_version == override_schema_version))
            result = connection.execute(s)
            if result.fetchone():
                return True

            s = sa.sql.select([self.release_check_error_table]) \
                .where((self.release_check_error_table.c.release_id == release_id) &
                       (self.release_check_error_table.c.override_schema_version == override_schema_version))
            result = connection.execute(s)
            if result.fetchone():
                return True

        return False

    def is_record_check_done(self, record_id, override_schema_version=None):
        with self.get_engine().begin() as connection:
            s = sa.sql.select([self.record_check_table]) \
                .where((self.record_check_table.c.record_id == record_id) &
                       (self.record_check_table.c.override_schema_version == override_schema_version))
            result = connection.execute(s)
            if result.fetchone():
                return True

            s = sa.sql.select([self.record_check_error_table]) \
                .where((self.record_check_error_table.c.record_id == record_id) &
                       (self.record_check_error_table.c.override_schema_version == override_schema_version))
            result = connection.execute(s)
            if result.fetchone():
                return True

        return False

    def mark_collection_file_store_done(self, collection_id, filename, warnings=None):
        with self.get_engine().begin() as connection:
            connection.execute(
                self.collection_file_table.update()
                    .where((self.collection_file_table.c.collection_id == collection_id) &
                           (self.collection_file_table.c.filename == filename))
                    .values(store_end_at=datetime.datetime.utcnow(),
                            warnings=warnings if warnings and len(warnings) > 0 else None,
                            )
            )

    def get_package_data(self, package_data_id):
        with self.get_engine().begin() as connection:
            s = sa.sql.select([self.package_data_table]) \
                .where(self.package_data_table.c.id == package_data_id)
            result = connection.execute(s)
            data_row = result.fetchone()
            return data_row['data']

    def get_data(self, data_id):
        with self.get_engine().begin() as connection:
            s = sa.sql.select([self.data_table]) \
                .where(self.data_table.c.id == data_id)
            result = connection.execute(s)
            data_row = result.fetchone()
            return data_row['data']

    def mark_collection_store_done(self, collection_id):
        with self.get_engine().begin() as connection:
            connection.execute(
                self.collection_table.update()
                    .where(self.collection_table.c.id == collection_id)
                    .values(store_end_at=datetime.datetime.utcnow())
            )
            # TODO Mark store_end_at on all files not yet marked

    def store_collection_file_errors(self, collection_id, file_name, url, errors):
        with self.get_engine().begin() as connection:
            s = sa.sql.select([self.collection_file_table]) \
                .where((self.collection_file_table.c.collection_id == collection_id) &
                       (self.collection_file_table.c.filename == file_name))
            result = connection.execute(s)

            collection_file_table_row = result.fetchone()

            if collection_file_table_row:
                return

            connection.execute(self.collection_file_table.insert(), {
                'collection_id': collection_id,
                'filename': file_name,
                'url': url,
                'errors': errors,
            })


class DatabaseStore:

    def __init__(self, database, collection_id, file_name, number, url=None):
        self.database = database
        self.collection_id = collection_id
        self.file_name = file_name
        self.url = url
        self.number = number
        self.connection = None
        self.transaction = None
        self.collection_file_id = None
        self.collection_file_item_id = None

    def __enter__(self):
        self.connection = self.database.get_engine().connect()
        self.transaction = self.connection.begin()

        # Collection File!
        s = sa.sql.select([self.database.collection_file_table]) \
            .where((self.database.collection_file_table.c.collection_id == self.collection_id) &
                   (self.database.collection_file_table.c.filename == self.file_name))
        result = self.connection.execute(s)

        collection_file_table_row = result.fetchone()

        if collection_file_table_row:
            self.collection_file_id = collection_file_table_row['id']
        else:
            value = self.connection.execute(self.database.collection_file_table.insert(), {
                'collection_id': self.collection_id,
                'filename': self.file_name,
                'store_start_at': datetime.datetime.utcnow(),
                'url': self.url,
                # TODO store warning?
            })
            # TODO look for unique key clashes, error appropriately!
            self.collection_file_id = value.inserted_primary_key[0]

        # Collection File Item!

        value = self.connection.execute(self.database.collection_file_item_table.insert(), {
            'collection_file_id': self.collection_file_id,
            'number': self.number,
            'store_start_at': datetime.datetime.utcnow(),
        })
        # TODO look for unique key clashes, error appropriately!
        self.collection_file_item_id = value.inserted_primary_key[0]

        return self

    def __exit__(self, type, value, traceback):

        if type:

            self.transaction.rollback()

            self.connection.close()

        else:

            self.connection.execute(
                self.database.collection_file_item_table.update()
                .where(self.database.collection_file_item_table.c.id == self.collection_file_item_id)
                .values(store_end_at=datetime.datetime.utcnow())
            )

            self.transaction.commit()

            self.connection.close()

    def insert_record(self, row, package_data):
        ocid = row.get('ocid')
        package_data_id = self.get_id_for_package_data(package_data)
        data_id = self.get_id_for_data(row)
        self.connection.execute(self.database.record_table.insert(), {
            'collection_file_item_id': self.collection_file_item_id,
            'ocid': ocid,
            'data_id': data_id,
            'package_data_id': package_data_id,
        })

    def insert_release(self, row, package_data):
        ocid = row.get('ocid')
        release_id = row.get('id')
        package_data_id = self.get_id_for_package_data(package_data)
        data_id = self.get_id_for_data(row)
        self.connection.execute(self.database.release_table.insert(), {
            'collection_file_item_id': self.collection_file_item_id,
            'release_id': release_id,
            'ocid': ocid,
            'data_id': data_id,
            'package_data_id': package_data_id,
        })

    def insert_compiled_release(self, row):
        ocid = row.get('ocid')
        data_id = self.get_id_for_data(row)
        self.connection.execute(self.database.compiled_release_table.insert(), {
            'collection_file_item_id': self.collection_file_item_id,
            'ocid': ocid,
            'data_id': data_id,
        })

    def get_id_for_package_data(self, package_data):

        hash_md5 = get_hash_md5_for_data(package_data)

        s = sa.sql.select([self.database.package_data_table]).where(self.database.package_data_table.c.hash_md5 == hash_md5)
        result = self.connection.execute(s)
        existing_table_row = result.fetchone()
        if existing_table_row:
            return existing_table_row.id
        else:
            return self.connection.execute(self.database.package_data_table.insert(), {
                'hash_md5': hash_md5,
                'data': package_data,
            }).inserted_primary_key[0]

    def get_id_for_data(self, data):

        hash_md5 = get_hash_md5_for_data(data)

        s = sa.sql.select([self.database.data_table]).where(self.database.data_table.c.hash_md5 == hash_md5)
        result = self.connection.execute(s)
        existing_table_row = result.fetchone()
        if existing_table_row:
            return existing_table_row.id
        else:
            return self.connection.execute(self.database.data_table.insert(), {
                'hash_md5': hash_md5,
                'data': data,
            }).inserted_primary_key[0]
