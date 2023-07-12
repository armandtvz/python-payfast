import logging



def configure_logging():
    loggers = [
        'payfast',
        'payfast.api',
        'payfast.django',
        'payfast.drf',
    ]
    for logger in loggers:
        logging.getLogger(logger).addHandler(logging.NullHandler())
