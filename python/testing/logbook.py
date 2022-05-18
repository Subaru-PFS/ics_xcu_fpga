import os

import numpy as np
import pandas as pd
import psycopg2
from astropy.io import fits

sequenceType = ['std_exposures_biases', 'std_exposures_darks', 'std_exposures_base', 'std_exposures_hours', 'std_exposures_vod_vog', 
                'std_exposures_bright_flats', 'std_exposures_low_flats', 'std_exposures_master_flats', 'std_exposures_fe55', 'std_exposures_qe', 'std_exposures_test']
oneOff = ['test_fe55_arm']

def cleanStr(text):
    return text.replace("'", '').strip()


def storeExposures(sequence, filelist, comments=''):
    comments = '' if comments is None else comments
    experimentId = Logbook.lastExperimentId() + 1
    for filepath in filelist:
        date, visit, ccd, exptype, exptime = exposureInfo(filepath)
        Logbook.newExposure(visit, experimentId, sequence, comments, date, ccd, exptype, exptime, filepath)


def exposureInfo(filepath):
    file = fits.open(filepath)
    head = file[0].header
    folder, fext = os.path.split(filepath)
    __, date = os.path.split(folder)
    fname, __ = os.path.splitext(fext)
    visit = int(fname[4:10])
    ccd = f'{head["W_ARM"][0]}{head["SPECNUM"]}'
    exptype = head['IMAGETYP']
    exptime = head['EXPTIME']
    return date, visit, ccd, exptype, exptime

def getSequence(sequence):
    if sequence in oneOff:
        return sequence

    sequence = f'std_exposures_{sequence}' if 'std_exposures_' not in sequence else sequence
    if sequence not in sequenceType:
        raise KeyError(f'unknown sequence type {sequence}')
    return sequence
    

def retrieveExposures(sequence, ccd, experiment=None):
    sequence = getSequence(sequence)
    if experiment is None:
        experiments = Logbook.fetchall(f"select experiment from exposure where sequence='{sequence}' and ccd='{ccd}'")
        if not experiments.size:
            raise ValueError(f'no {sequence} available with {ccd}')
        experiment = experiments.max()
    exposures = Logbook.fetchall(f'select * from exposure where experiment={experiment}')
    return pd.DataFrame(exposures, columns=['visit', 'experiment', 'sequence', 'comments', 'date', 'ccd', 'exptype', 'exptime', 'filepath']).sort_values('visit').reset_index(drop=True)

def describeExperiments(sequence, ccd):
    sequence = getSequence(sequence)
    columns = 'experiment,sequence,comments,date,ccd' 
    experiments = Logbook.fetchall(f"select experiment from exposure where sequence='{sequence}' and ccd='{ccd}'")
    if not experiments.size:
        raise ValueError(f'no {sequence} available with {ccd}')
    count = np.bincount(experiments[:, 0])
    experiments = np.unique(experiments)
    descp = [Logbook.fetchone(f'select {columns} from exposure where experiment={experiment} order by visit limit 1') for experiment in experiments]
    descp = pd.DataFrame(np.array(descp), columns=columns.split(','))
    descp['exposureCount'] = count[experiments]
    return descp.set_index('experiment')


class Logbook:
    @staticmethod
    def connect():
        prop = "dbname='exposureLog' user='pfs' password='2394f4s3d' host='tron' port='5432'"
        return psycopg2.connect(prop)

    @staticmethod
    def fetchall(query):
        with Logbook.connect() as conn:
            with conn.cursor() as curs:
                curs.execute(query)
                return np.array(curs.fetchall())
            
    @staticmethod
    def fetchone(query):
        with Logbook.connect() as conn:
            with conn.cursor() as curs:
                curs.execute(query)
                return np.array(curs.fetchone())

    @staticmethod
    def update(query):
        with Logbook.connect() as conn:
            with conn.cursor() as curs:
                curs.execute(query)
            conn.commit()

    @staticmethod
    def lastExperimentId():
        with Logbook.connect() as conn:
            with conn.cursor() as curs:
                curs.execute("""SELECT MAX(experiment) FROM exposure""")
                (experimentId,) = curs.fetchone()
                experimentId = experimentId if experimentId is not None else 0
                return experimentId

    @staticmethod
    def newExposure(visit, experimentId, sequence, comments, date, ccd, exptype, exptime, filepath):
        comments = cleanStr(comments)
        query = """INSERT INTO exposure VALUES (%d, %d, '%s', '%s', '%s', '%s', '%s', %.1f, '%s');""" % (visit,
                                                                                                         experimentId,
                                                                                                         sequence,
                                                                                                         comments,
                                                                                                         date,
                                                                                                         ccd,
                                                                                                         exptype,
                                                                                                         exptime,
                                                                                                         filepath)

        Logbook.update(query=query)

    @staticmethod
    def setColumnValue(visit, column, value):
        if isinstance(value, str):
            fmt = '"{:s}"'
            value = cleanStr(value)
        elif isinstance(value, int):
            fmt = '{:d}'
        elif isinstance(value, float):
            fmt = '{:.1f}'
        else:
            raise TypeError(f'Unknown Type {type(value)}')

        value = fmt.format(value)

        query = """UPDATE Exposure SET %s = %s WHERE visit=%d""" % (column, value, visit)
        Logbook.update(query=query)
