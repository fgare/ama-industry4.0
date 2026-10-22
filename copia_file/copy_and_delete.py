import sys
from pathlib import Path
import shutil
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime


def setup_logger(log_dir="logs", log_name="file_mover.log"):
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)

    logger = logging.getLogger("file_logger")
    logger.setLevel(logging.INFO)

    handler = TimedRotatingFileHandler(
        filename=log_path / log_name,
        when='midnight', # Rotazione a mezzanotte
        interval=1,
        backupCount=30, # Numero di log giornalieri da conservare
        encoding='utf-8'
    )
    formatter = logging.Formatter(
        '%(asctime)s %(levelname)s %(message)s',
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger

def sposta_file(sorgente_path, destinazioni, logger) -> int:
    sorgente = Path(sorgente_path)
    destinazioni = [Path(dest) for dest in destinazioni]

    # Controlli
    if not sorgente.is_dir():
        logger.error(f"La sorgente '{sorgente}' non è una cartella valida.")
        return

    for dest in destinazioni:
        if not dest.is_dir():
            logger.error(f"La destinazione '{dest}' non è una cartella valida.")
            return

    file_spostati: int = 0
    # Elabora tutti i file nella cartella sorgente
    for file in sorgente.iterdir():
        if file.is_file():
            for dest in destinazioni:
                shutil.copy2(file, dest / file.name)
                logger.info(f"Copiato '{file.name}' in '{dest}'")
            file.unlink()
            logger.info(f"Eliminato '{file.name}' da '{sorgente}'")
            file_spostati += 1
    
    return file_spostati


if __name__ == "__main__":
    start = datetime.now()
    logger = setup_logger()
    logger.info("Inizio elaborazione")

    if len(sys.argv) < 3:
        logger.critical("Uso: python sposta_e_copia.py <sorgente> <dest1> [<dest2> ...]")
        sys.exit(1)

    sorgente = sys.argv[1]
    destinazioni = sys.argv[2:]

    tot = sposta_file(sorgente, destinazioni, logger)
    logger.info("Fine elaborazione. Spostati %d file in %s", tot, datetime.now()-start)
