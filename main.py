import sys, os, logging, time, signal, glob, shutil
import logging.handlers
from datetime import datetime
from threading import Event, Thread

from ffmpeg_recorder import FFmpegRecorder, Timeout
from slack_bot import SlackBot
import logger as Logger

g_event = Event()
g_monitoring = False
g_logger = None
g_slack = None

TS_OFFSET = (datetime.fromtimestamp(1592429000) - datetime.utcfromtimestamp(1592429000)).total_seconds()


LOG_LEVELS = {
    'debug':    logging.DEBUG,
    'info':     logging.INFO,
    'warning':  logging.WARNING,
    'error':    logging.ERROR,
    'critical': logging.CRITICAL
    }

class SlackBotWrapper:
    def __init__(self, slack_bot):
        self._bot = slack_bot

    def info(self, title, text):
        if self._bot:
            try:
                self._bot.post_info(title, text)
            except:
                g_logger.exception("SlackBot Info Error")

    def warning(self, title, text):
        if self._bot:
            try:
                self._bot.post_warning(title, text)
            except:
                g_logger.exception("SlackBot Warning Error")

    def alert(self, title, text):
        if self._bot:
            try:
                self._bot.post_alert(title, text)
            except:
                g_logger.exception("SlackBot Alert Error")


def monitor(name, out_path, interval, saving_period, restart_threshold):
    today_ts = None
    tomorrow_ts = None
    remove_at_ts = None

    filename = None
    file_ts = int(time.time())
    file_size = 0

    error_counter = 0
    def _is_notified(elapsed_secs, threshold, counter):
        if elapsed_secs/threshold > counter+1:
            return True
        else:
            return False

    g_logger.info("Monitoring thread starts")
    while g_monitoring:
        try:
            # Create the directory 3 minutes ahead of the time
            ts = int(time.time()) + TS_OFFSET
            new_today_ts = int(ts/(3600*24))*3600*24
            new_tomorrow_ts = int((ts+180)/(3600*24))*3600*24
            if new_today_ts != today_ts:
                today_ts = new_today_ts
                tv = datetime.fromtimestamp(today_ts-TS_OFFSET)
                today_path = os.path.join(out_path, tv.strftime("%Y%m%d"))
                if not os.path.isdir(today_path):
                    g_logger.info("Making directory %s" % today_path)
                    os.mkdir(today_path)
            if new_tomorrow_ts != new_today_ts and new_tomorrow_ts != tomorrow_ts:
                tomorrow_ts = new_tomorrow_ts
                tv = datetime.fromtimestamp(tomorrow_ts-TS_OFFSET)
                tomorrow_path = os.path.join(out_path, tv.strftime("%Y%m%d"))
                if not os.path.isdir(tomorrow_path):
                    g_logger.info("Making directory %s" % tomorrow_ts)
                    os.mkdir(tomorrow_path)
            
            # Delete old data
            current_dates = glob.glob(os.path.join(out_path, '*'))
            current_dates.sort()
            new_remove_at_ts = int((ts-saving_period*24*3600)/(3600*24))*3600*24
            if new_remove_at_ts != remove_at_ts:
                remove_at_ts = new_remove_at_ts
                tv = datetime.fromtimestamp(remove_at_ts-TS_OFFSET)
                remove_at_path = os.path.join(out_path, tv.strftime("%Y%m%d"))
                for p in current_dates:
                    if p >= remove_at_path:
                        break
                    else:
                        shutil.rmtree(p)

            # Check file name & file size
            # Raise alert if size has not been change for 1 minute
            new_filename = g_recorder.current_filename()
            new_file_ts = int(time.time())
            if new_filename == None:
                new_file_size = 0
            else:
                try:
                    new_file_size = os.path.getsize(new_filename)
                except OSError as e:
                    g_logger.error("Can't get size of file %s: %s" % (new_filename, e))
                    g_slack.alert("IP Cam - Filesize", "Can't get size of file %s: %s" % (new_filename, e))
                    new_file_size = 0
               
            # If filename is different
            if new_filename != filename or new_file_size != file_size:
                if new_filename != filename:
                    g_slack.info("IP Cam - Filename", "New file name: %s" % new_filename)
                    filename = new_filename
                file_ts = new_file_ts
                file_size = new_file_size
                error_counter = 0
            elif new_file_ts - file_ts > restart_threshold:
                msg = "Size of %s has not changed after %d seconds, restart the recording process now" % (
                            filename, new_file_ts - file_ts)
                g_logger.error(msg)

                if _is_notifed(new_file_ts-file_ts, restart_threshold, error_counter):
                    error_counter += 1
                    g_slack.alert("IP Cam - FFmpeg Recording Process Stucks", msg)
                while True:
                    try:
                        g_recorder.restart(5)
                        break
                    except Timeout as e:
                        g_logger.critical(e)
                        g_slack.alert("IP Cam - FFmpeg Recording Restart TIMEOUT", "%s\nTrying again..." % e)
                g_logger.info("FFmpeg recording process restarted successfully")
                g_slack.info("IP Cam - Restart", "FFmpeg recording process restarted successfully")
        except:
            g_logger.exception("Monitoring thread has ERROR")
            g_slack.alert("IP Cam - Monitoring Thread ERROR", "Something went wrong in the monitoring thread, please check logs")

        if g_event.wait(interval):
            break

    g_logger.info("Monitoring thread stopped")

def system_signal(sig_num, stack_frame):
    g_logger.info("Reciving SYSTEM SIGNAL: %s" % sig_num)
    g_monitoring = False
    g_event.set()

    g_recorder.stop()
    g_monitor_thread.join()


if __name__ == '__main__':
    from argparse import ArgumentParser
    parser = ArgumentParser()

    # General arguments
    parser.add_argument('--protocol', type=str, default='rtsp', choices=['rtsp'], help='Input protocol')
    parser.add_argument('--src', type=str, help='Source of videostream')
    parser.add_argument('--enable_audio', action='store_true', help='Allow record audio with video')
    parser.add_argument('--segment_time', type=int, default=1800, help='Length of each segment, in seconds')
    parser.add_argument('--out_path', type=str, help='Location of output videos')
    parser.add_argument('--out_prefix', type=str, help='Prefix for the output files')
    parser.add_argument('--monitor_interval', type=int, default=5, help='Monitoring interval, in secondss')
    parser.add_argument('--saving_period', type=int, default=15, help='Period of saving videos, in days')
    parser.add_argument('--restart_threshold', type=int, default=30, 
                        help='Restart threshold in seconds, if file size is the same after this seconds, process will be restarted')
    parser.add_argument('--log_path', type=str, default='/tmp', help='Location of logs')
    parser.add_argument('--log_level', type=str, default='error', choices=['debug', 'info', 'warning', 'error', 'critical'],
                        help='Level of the console log')

    # Arguments for slack
    parser.add_argument('--slack_channel', type=str, default='', help='For notifying the status of the recording')
    parser.add_argument('--slack_notifee', type=str, default='', help='Notifying if something when wrong')

    args = parser.parse_args()

    # Init the logger
    logger = Logger.init_logger(args.out_prefix, args.log_path, logging.DEBUG, LOG_LEVELS[args.log_level], args.saving_period)
    ffmpeg_logger = Logger.get_adapter(logger, '=== FFMPEG RECODER ===')
    g_logger = logger

    # Init the slack
    if args.slack_channel:
        slack_token = os.environ.get('SLACK_TOKEN', None)
        g_slack = SlackBotWrapper(SlackBot(slack_token ,args.slack_channel, args.slack_notifee))
    else:
        g_slack = SlackBotWrapper(None)

    # Init the recoder and start recording
    g_recorder = FFmpegRecorder(args.protocol, args.src, args.enable_audio, args.segment_time, args.out_path,
                              args.out_prefix, None, ffmpeg_logger)
    
    # Start monitoring thread
    g_monitor_thread = Thread(target=monitor, args=(args.out_prefix, args.out_path, args.monitor_interval, args.saving_period,
                                                    args.restart_threshold))
    g_monitoring = True
    g_event.clear()
    g_monitor_thread.start()

    # Start recorder
    signal.signal(signal.SIGINT, system_signal)
    signal.signal(signal.SIGTERM, system_signal)
    g_recorder.start()
    g_slack.alert("IP Cam - Recording Starts", "FFmpeg Recording starts for %s, file length %d minutes, saving period %d days, " % (
                  args.out_prefix, args.segment_time/60, args.saving_period))

    # Wait for recording to stop
    while True:
        if g_event.wait(args.monitor_interval):
            break

    # Do something
    g_slack.alert("IP Cam - Recording Stops", "FFmpeg Recording for %s stopped" % args.out_prefix)

