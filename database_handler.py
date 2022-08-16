import pymysql
import datetime


class MySQLdbHandler:

    def __init__(self, db_params):
        """
        db_params is dict with params of db like
            {
            'host': 'localhost',
             'user':'admin',
             'db':'experiment',
             'password':'admin'
             'experiment_name':1'
             }
        """
        self._db_name = "exp" + str(db_params["experiment_name"])
        self._db_params = db_params
        #pass

    def create_database(self):
        print("create database")

        con = pymysql.connect(host=self._db_params["host"],
                              user=self._db_params["user"],
                              password=self._db_params["password"],
                              # db='experiment',
                              charset='utf8mb4',
                              cursorclass=pymysql.cursors.DictCursor)

        cur = con.cursor()

        cur.execute("CREATE DATABASE IF NOT EXISTS {}".format(self._db_name))
        cur.execute("use {}".format(self._db_name))
        con.close()

    def create_data_table(self, sensor_name):
        """
        raw_data is table for data from all devices - one sensor - one table:
        +-----------+----------------------+------+-----+-------------------+-----------------------------+
        | Field     | Type                 | Null | Key | Default           | Extra                       |
        +-----------+----------------------+------+-----+-------------------+-----------------------------+
        | data_id   | bigint(20) unsigned  | NO   | PRI | NULL              | auto_increment              |
        | time      | timestamp            | NO   |     | CURRENT_TIMESTAMP | on update CURRENT_TIMESTAMP |
        | sensor_id | smallint(5) unsigned | YES  |     | NULL              |                             |
        | data      | double               | YES  |     | NULL              |                             |
        +-----------+----------------------+------+-----+-------------------+-----------------------------+
        """

        con = pymysql.connect(host=self._db_params["host"],
                          user=self._db_params["user"],
                          password=self._db_params["password"],
                          charset='utf8mb4',
                          cursorclass=pymysql.cursors.DictCursor)

        cur = con.cursor()
        cur.execute("use {}".format(self._db_name))

        cur.execute('create table if not exists {}'
                    ' (data_id bigint unsigned primary key not null auto_increment,'
                    ' time timestamp,'
                    ' data double)'.format(sensor_name)
                    )

        cur.execute('describe {}'.format(sensor_name))
        print(cur.fetchall())
        con.close()


    def create_log_table(self, log_name):
        """
        xxx_logs is tables for different log messages
        +--------+----------------------+------+-----+-------------------+-----------------------------+
        | Field  | Type                 | Null | Key | Default           | Extra                       |
        +--------+----------------------+------+-----+-------------------+-----------------------------+
        | log_id | bigint(20) unsigned  | NO   | PRI | NULL              | auto_increment              |
        | time   | timestamp            | NO   |     | CURRENT_TIMESTAMP | on update CURRENT_TIMESTAMP |
        | level  | tinyint(4)           | YES  |     | NULL              |                             |
        | node   | varchar(100)         | YES  |     | NULL              |                             |
        | msg    | varchar(500)        | YES  |     | NULL              |                             |
        +--------+----------------------+------+-----+-------------------+-----------------------------+
        """
        con = pymysql.connect(host=self._db_params["host"],
                              user=self._db_params["user"],
                              password=self._db_params["password"],
                              charset='utf8mb4',
                              cursorclass=pymysql.cursors.DictCursor)

        cur = con.cursor()
        cur.execute("use {}".format(self._db_name))

        cur.execute('create table if not exists {}'
                    ' ( log_id bigint unsigned primary key not null auto_increment,'
                    ' time timestamp,'
                    ' node varchar(100),'
                    ' message varchar(500) )'.format(log_name)
                    )

        cur.execute('describe {}'.format(log_name))
        print(cur.fetchall())
        con.close()

    def add_data_in_table(self, table_name, data):
        con = pymysql.connect(host=self._db_params["host"],
                              user=self._db_params["user"],
                              password=self._db_params["password"],
                              charset='utf8mb4',
                              cursorclass=pymysql.cursors.DictCursor)

        cur = con.cursor()

        cur.execute("use {}".format(self._db_name))
        time_ = datetime.datetime.now().strftime('%Y_%m_%d %H:%M:%S')

        comm_str = 'insert into {} (time, data) values( "{}", "{}" )'.format(
            table_name, time_, data)

        print("comm_str: {}".format(comm_str))

        cur.execute(comm_str)

        cur.execute('commit')
        con.close()

    def add_log_in_table(self, table_name, node, log):
        con = pymysql.connect(host=self._db_params["host"],
                              user=self._db_params["user"],
                              password=self._db_params["password"],
                              charset='utf8mb4',
                              cursorclass=pymysql.cursors.DictCursor)

        cur = con.cursor()

        cur.execute("use {}".format(self._db_name))
        time_ = datetime.datetime.now().strftime('%Y_%m_%d %H:%M:%S')

        comm_str = 'insert into {}' \
                   '(time, node, message)' \
                   'values("{}", "{}", "{}")'.format(table_name, time_, node, log)

        try:
            cur.execute(comm_str)
        except Exception as e:
            print("Error while saving logs from :")
            print(e)

        cur.execute('commit')
        con.close()


if __name__ == "__main__":

    # this is secret dict with important data, that we have to store in another config file
    _db = {
        "host": 'localhost',
        "user": 'admin',
        "db": 'experiment',
        "password": "admin",
        "experiment_number": "1"
    }

    dbh1 = MySQLdbHandler(_db)
    dbh1.create_database()
    dbh1.create_log_table("important_logs")
    dbh1.add_log_in_table("important_logs", "node1", "warn warn warn warn!!!!")
    dbh1.add_log_in_table("important_logs", "node1", "warn warn warn warn!!!!")
    dbh1.add_log_in_table("important_logs", "node1", "rrrrrrrrrrrrrrrrrrr")
    dbh1.add_log_in_table("important_logs", "node1", "warn warn warn warn!!!!")
    dbh1.create_data_table(sensor_name="dht11_data")
    dbh1.add_data_in_table(table_name="dht11_data", data=123.456)
