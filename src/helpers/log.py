import logging

class Logger(logging.Formatter):
    grey = '\x1b[38;21m'
    blue = '\x1b[38;5;39m'
    yellow = '\x1b[38;5;226m'
    red = '\x1b[38;5;196m'
    bold_red = '\x1b[31;1m'
    reset = '\x1b[0m'
    ___format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"

    def __init__(self):
        super().__init__()
        self.FORMAT = {
            logging.DEBUG: self.grey + self.___format + self.reset,
            logging.INFO: self.blue + self.___format + self.reset,
            logging.WARNING: self.yellow + self.___format + self.reset,
            logging.ERROR: self.red + self.___format + self.reset,
            logging.CRITICAL: self.bold_red + self.___format + self.reset
        }

    def format(self, record):
        log_severity = self.FORMAT.get(record.levelno)
        __formatter = logging.Formatter(log_severity)
        return __formatter.format(record)