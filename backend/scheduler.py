from apscheduler.schedulers.background import BackgroundScheduler

_scheduler = BackgroundScheduler()


def start_scheduler():
    # TODO: register monitor jobs from config
    _scheduler.start()


def stop_scheduler():
    _scheduler.shutdown(wait=False)
