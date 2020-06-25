import logging, os


class CustomAdapter(logging.LoggerAdapter):
    def __init__(self, logger, name):
        super(CustomAdapter, self).__init__(logger, {})
        self._name = name

    def process(self, msg, kwargs):
        return "%s %s" % (self._name, msg), kwargs


def init_logger(name, path, file_level, console_level, backup_count):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s %(levelname)s\t%(message)s", "%Y-%m-%d %H:%M:%S")

    # Init console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Init file handler - all
    log_path = os.path.join(path, name)
    if not os.path.isdir(log_path):
        os.mkdir(log_path)
    filename_all = os.path.join(log_path, 'all.log')
    all_handler = logging.handlers.TimedRotatingFileHandler(filename=filename_all, when='midnight', backupCount=backup_count)
    all_handler.setLevel(file_level)
    all_handler.setFormatter(formatter)
    logger.addHandler(all_handler)

    # Init file handler - error
    filename_err = os.path.join(log_path, 'error.log')
    err_handler = logging.handlers.TimedRotatingFileHandler(filename=filename_err, when='midnight', backupCount=backup_count)
    err_handler.setLevel(logging.ERROR)
    err_handler.setFormatter(formatter)
    logger.addHandler(err_handler)
    
    return logger


def get_adapter(logger, name):
    return CustomAdapter(logger, name)

