# FEDERICO GAREGNANI - MIES SRL
# Legge i file .Trend della macchina ERSA saldature selettive e
# scrive un nuovo file con lo stesso contenuto ma estensione .csv

from pathlib import Path, PurePath
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
import pickle
import sys
import csv
from io import StringIO
import xml.etree.ElementTree as ET


MACHINE_NAME: str = "Ersa Linea saldature selettive" # deve coincidere con il nome di Oneview
MAX_OUTPUT_FILESIZE: int = 9 # dimensione massima del file di output [KB]


def setup_logger(log_dir="logs", log_name="converter"):
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)

    logger = logging.getLogger(log_name)
    logger.setLevel(logging.INFO)

    handler = TimedRotatingFileHandler(
        filename=log_path.joinpath(log_name + ".log"),
        when='midnight', # Rotazione a mezzanotte
        interval=1,
        backupCount=60, # Numero di log giornalieri da conservare
        encoding='utf-8'
    )
    formatter = logging.Formatter(
        '%(asctime)s %(levelname)s %(message)s',
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    if not len(logger.handlers):
        logger.addHandler(handler)

    return logger

logger: logging.Logger = setup_logger(log_name=MACHINE_NAME)


class LastRun:
    """
    Memorizza la data dell'ultimo file convertito
    """
    last_trend: datetime
    last_xml: datetime

    def __init__(self, name = "mem.bin", autosave = False):
        self.last_trend = datetime(1970,1,1,0,0,0)
        self.last_xml = datetime(1970,1,1,0,0,0)
        self.filename = name
        self.autosave = autosave

    def commit(self) -> None:
        mem_file = Path.cwd().joinpath("mem", self.filename)
        mem_file.parent.mkdir(parents=True, exist_ok=True) # Crea la cartella 'mem' se non esiste

        try:
            with open(mem_file, 'wb') as f:
                pickle.dump(self, f)
            logger.debug("File '%s' aggiornato", self.filename)
        except Exception as e:
            logger.critical("Generic exception\n", exc_info=e)
            raise e
    
    @staticmethod
    def get_instance(file_path: Path = Path.cwd().joinpath("mem", "mem.bin")) -> 'LastRun':
        if file_path.exists() and file_path.is_file():
            try:
                with open(file_path, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                logger.critical("Errore nella lettura del file di memoria al percorso %s\n", file_path, exc_info=e)
                raise e
        else:
            logger.info("Il file di memoria '%s' non esiste, utilizzo l'istanza di default", file_path)
            return LastRun()
    
    def update_last_trend(self, new_date: datetime) -> None:
        self.last_trend = new_date
        if self.autosave: self.commit() # sovrascrive il vecchio file

    def update_last_xml(self, new_date: datetime) -> None:
        self.last_xml = new_date
        if self.autosave: self.commit()


# def nuovi_file(cartella: Path, lastdate: datetime, extention: str) -> tuple[list[Path], datetime]:
#     """
#     Ritorna la lista di file con data di modifica successiva alla data fornita del campo lastdate
#     """
#     extention = extention.lower()
#     # elenco dei file nella cartella
#     files = [f for f in cartella.iterdir() if f.suffix.lower()==extention and f.is_file()]
#     logger.debug("In '%s' sono presenti %d file", cartella, len(files))

#     # elenco dei file successivi all'utima esecuzione
#     new_files = [f for f in files if datetime.fromtimestamp(f.stat().st_mtime) >= lastdate]
#     # aggiorna la data del file più recente
#     if new_files:
#         maxtime = max(f.stat().st_mtime for f in new_files)
#         lastdate = datetime.fromtimestamp(maxtime)
#         logger.debug("Nuova data del file piu' recente: '%s'", lastdate)
    
#     return (new_files, lastdate)

def nuovi_file(cartella: Path, lastdate: datetime, extention: str) -> tuple[list[Path], datetime]:
    """
    Ritorna la lista di file con data di modifica successiva alla data fornita del campo lastdate.
    Gestisce errori di rete intermittenti su share SMB (WinError 59).
    """
    extention = extention.lower()

    # elenco dei file nella cartella
    files = [f for f in cartella.iterdir() if f.suffix.lower() == extention and f.is_file()]
    logger.debug("In '%s' sono presenti %d file", cartella, len(files))

    # elenco dei file successivi all'ultima esecuzione
    # stat() viene chiamato una sola volta per file e gli OSError sono gestiti
    new_files = []
    max_mtime: float | None = None

    for f in files:
        try:
            mtime = f.stat().st_mtime
        except OSError as e:
            logger.warning("Impossibile leggere le proprietà di '%s', file ignorato: %s", f, e)
            continue

        if datetime.fromtimestamp(mtime) >= lastdate:
            new_files.append(f)
            if max_mtime is None or mtime > max_mtime:
                max_mtime = mtime

    # aggiorna la data del file più recente
    if new_files and max_mtime is not None:
        lastdate = datetime.fromtimestamp(max_mtime)
        logger.debug("Nuova data del file piu' recente: '%s'", lastdate)

    return (new_files, lastdate)


def convert_trend_to_csv(src_path: Path, write_folder: Path):
    """
    Converte il file ricevuto come argomento con estensione .Trend in un file .csv
    """
    original_name_no_ext = src_path.stem.replace("_","") # nome del file e rimuove "_"
    
    file_pieces: list[StringIO] = list()
    with open(src_path, 'r', encoding='utf-8') as srcfile:
        reader = csv.reader(srcfile, delimiter=';')
        header = next(reader)
        rows = list(reader)
        file_pieces = split_large_file(rows, header, MAX_OUTPUT_FILESIZE)
    logger.debug("Il file e' stato spezzato in %d file", len(file_pieces))
    
    for idx, p in enumerate(file_pieces):
        original_name_no_ext = src_path.stem.replace("_","") # nome del file e rimuove "_"
        dest_filename = f"{MACHINE_NAME}_{original_name_no_ext}_{str(idx)}.csv"
        dest_path = PurePath.joinpath(write_folder, dest_filename)

        r = csv.reader(p, delimiter=';')

        with open(dest_path, 'w', newline='', encoding='utf-8') as dest:
            w = csv.writer(dest, delimiter=';')
            w.writerow(next(r)) # scrive header
            # scrive il file una riga alla volta
            for row in r:
                if row and row[-1]=="":
                    row = row[:-1] # rimuove colonna vuota finale
                w.writerow(row)

        logger.debug("Scritto file '%s'", dest_path)

    return len(file_pieces)


def convert_xml_to_csv(scr_path: Path, write_folder: Path):
    filetree = ET.parse(scr_path)
    root = filetree.getroot()

    params = {}

    # Estrae i parametri di configurazione
    for p in root.findall(".//processingParameters/parameter"):
        name = p.get("name")
        value = p.get("value")
        params[name] = value

    # Estrae i dati fisici di misurazione della macchina (Temperature, Tempi, ecc.)
    for m in root.findall(".//measuring/channel"):
        name = m.get("name")
        sample = m.find("sample")
        if sample is not None:
            value = sample.get("value")
            params[name] = value

    # Usa il nome originale del file (senza estensione) per generare il file CSV,
    # in questo modo è impossibile che i file si sovrascrivano a vicenda.
    original_name = scr_path.stem
    filename = f"{MACHINE_NAME}_XML_{original_name}.csv"
    dest_path = write_folder.joinpath(filename)

    # Rinomina la chiave 'Avvio' in 'Time' in modo sicuro, mantenendo l'ordine
    params = {("Time" if k == "Avvio" else k): v for k, v in params.items()}

    # Scrive il file csv
    with open(dest_path, 'w', newline='', encoding='utf-8') as dest:
        w = csv.DictWriter(dest, fieldnames=params.keys(), delimiter=';')
        w.writeheader()
        w.writerow(params)
        
    logger.debug("Scritto file '%s' da '%s'", dest_path.name, scr_path.name)

    return int(1)


def split_large_file(rows: list[str], header: list[str], max_dim: int) -> list[StringIO]:
    """
    Separa un file CSV in tanti file CSV di dimensioni inferiori ad una dimensione fissata
    """

    def compute_file_size(rows, header) -> int:
        """
        Simula la dimensione su disco di un file CSV con le righe fornite in input
        """
        buf = StringIO()
        w = csv.writer(buf)
        w.writerow(header)
        w.writerows(rows)
        return len(buf.getvalue().encode('utf-8'))

    if compute_file_size(rows, header) > max_dim * 1024:
        logger.debug("File troppo grande, lo divido in due meta'. Numero righe = %d'", len(rows))
        # pieces = list()
        half_idx = len(rows) // 2
        p1 = split_large_file(rows[:half_idx], header, max_dim) # prima meta' delle righe
        logger.debug("Dimensione di p1: %d", len(p1))
        p2 = split_large_file(rows[half_idx:], header, max_dim) # seconda meta'
        logger.debug("Dimensione di p2: %d", len(p2))
        pieces: list = p1+p2
        # logger.debug("Numero di parti del file: %d", len(pieces))
        return pieces
    else:
        buf = StringIO()
        w = csv.writer(buf, delimiter=';')
        w.writerow(header)
        w.writerows(rows)
        buf.seek(0)
        # logger.debug("Righe: %s", buf.getvalue())
        return [buf]


def compute_trend(trend_f, write_f, lastrun):
    new_files, lastdate = nuovi_file(trend_f, lastrun.last_trend, ".trend")
    lastrun.update_last_trend(lastdate)
    logger.info("Sono presenti %d nuovi file Trend", len(new_files))

    n = 0
    for f in list(new_files):
        # f contiene già l'intero percorso (es. history_trend\file.trend)
        scr_path = f 

        try:
            added_files = convert_trend_to_csv(scr_path, write_f)
            n += added_files
            logger.debug("Scritti %d file da '%s'", added_files, scr_path.name)
        except Exception as e:
            logger.exception("%s", str(e))
            new_files.remove(f)
    
    logger.info("Scritti %d file totali da %d originali '.trend'", n, len(new_files))


def compute_xml(xml_f, write_f, lastrun):
    new_files, lastdate = nuovi_file(xml_f, lastrun.last_xml, ".xml")
    lastrun.update_last_xml(lastdate)
    logger.debug("Sono presenti %d nuovi file XML", len(new_files))

    n = 0
    for f in list(new_files): # Meglio usare list() se prevedi di rimuovere elementi
        # f contiene già l'intero percorso
        scr_path = f 

        try:
            n += convert_xml_to_csv(scr_path, write_f)
        except Exception as e:
            logger.exception("%s", str(e))
            # se si genera un'eccezione nella conversione rimuovo il file
            new_files.remove(f)
            n -= 1

    logger.info("Scritti %d file da file '.XML'", n)


def main():
    try:
        read_trend_folder: Path = Path(sys.argv[1])
        read_xml_folder: Path = Path(sys.argv[2])
        write_folder: Path = Path(sys.argv[3])
    except Exception as e:
        logger.exception("%s", str(e))
        return
    logger.debug("Percorsi di in/out riconosciuti")

    # se la cartella di output non esiste, viene creata
    write_folder.mkdir(parents=True, exist_ok=True)
    
    lastrun: LastRun = LastRun.get_instance()
    logger.debug("Date degli ultimi file letti: TREND '%s'\tXML '%s'", lastrun.last_trend, lastrun.last_xml)

    # FILE TREND
    compute_trend(read_trend_folder, write_folder, lastrun)

    # FILE XML
    compute_xml(read_xml_folder, write_folder, lastrun)
    
    lastrun.commit()


if __name__ == "__main__":
    start = datetime.now()
    logger.info("Convertitore avviato")

    try:
        main()
    except Exception as e:
        logger.exception(e)

    logger.info("Terminato in %s", datetime.now()-start)