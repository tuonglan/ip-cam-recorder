import subprocess, re, os, io, time
from threading import Thread, Event
from queue import Queue

FILE_PTT = re.compile(".+?'(.+?)'.*")

class Timeout(Exception): pass

class FFmpegRecorder:
    def __init__(self, protocol, video_src, audio_enabled, segment_time, out_path, out_prefix, std_cb, logger):
        self._video_src = video_src
        self._segment_time = segment_time
        self._out_path = out_path
        self._out_prefix = out_prefix
        self._std_cb = std_cb
        self._logger = logger
    
        self._running = False
        self._recording = False
        self._recording_thread = None
        self._process = None
        self._lines = Queue()
        self._event = Event()

        # Set input
        cmd = ["ffmpeg"]
        if protocol == 'rtsp':
            cmd.extend(['-rtsp_transport', 'tcp'])
        else:
            raise Exception("Invalid source protocol: %s" % protocol)
        cmd.extend(['-i', video_src])

        # Set video & audio format
        if audio_enabled:
            cmd.extend(['-c:v', 'copy', '-c:a', 'copy'])
        else:
            cmd.extend(['-c:v', 'copy'])

        # Set output
        out_ptt = os.path.join(out_path,"%Y%m%d", "%Y%m%d-%H%M%S.mp4")
        cmd.extend(['-f', 'segment', '-segment_time', str(segment_time), '-segment_format', 'mp4', '-reset_timestamps', '1', 
                    '-segment_atclocktime', '1', '-strftime', '1', out_ptt])
        
        self._cmd = cmd
    
        # Init internal value
        self._current_filename = None

    def _process_stdout(self):
        self._logger.info("STD Thread starts")
        while self._recording or not self._lines.empty():
            line = self._lines.get()
            if line != None:
                self._logger.debug("Recording STDOUT: %s" % line)
                if self._std_cb:
                    self._std_cb(line)
                if line.startswith('[segment') and 'writing' in line:
                    m = FILE_PTT.match(line)
                    if m:
                        self._current_filename = m.group(1)
                        self._logger.debug("New file has been created: %s" % self._current_filename)
                    else:
                        self._logger.error("Can't find file name in string: \"%s\"" % line)
            else:
                self._logger.debug("Buffer return None, stop processing stdout thread!")
                break
        
        self._logger.info("STD Thread stopped")

    def _run(self):
        self._logger.info("Recording Process starts")
        self._recording = True
        stdout_thread = Thread(target=self._process_stdout)
        stdout_thread.start()

        try:
            # Keep running the process
            while self._running:
                self._logger.info("Running command \"%s\"" % self._cmd)
                self._process = subprocess.Popen(self._cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                line = self._process.stdout.read(100)
                buf = io.StringIO()
                while line:
                    for c in line.decode('utf-8'):
                        if c == '\n':
                            self._lines.put_nowait(buf.getvalue())
                            buf = io.StringIO()
                        elif c == '\r':
                            buf = io.StringIO()
                        else:
                            buf.write(c)
                    line = self._process.stdout.read(100)
                
                if self._running:
                    self._logger.error("Recording process stop unexpectedly, restarting automatically after 3 seconds...")
                    self._event.wait(3)
        except Exception as e:
            self._logger.exception("FFmpeg has critical error: %s" % e)
        finally:
            # Set event flag
            self._recording = False
            self._lines.put_nowait(None)
            stdout_thread.join()
            self._logger.info("Recording process stopped")

    def start(self):
        self._running = True
        self._event.clear()
        self._recording_thread = Thread(target=self._run)
        self._recording_thread.start()

    def stop(self, timeout=0):
        # Terminate if not stopped
        self._logger.debug("FFmpegRecorder::Stop called")
        self._running = False
        self._event.set()
        start_ts = time.time()
        if self._process and self._process.poll() == None:
            self._process.terminate()
            self._recording_thread.join(3)
            while self._recording_thread.is_alive():
                if timeout > 0 and time.time() - start_ts > timeout:
                    raise Timeout("Timeout: FFmpeg Recoder can't stop after %s seconds" % timeout)
                self._logger.error("Can't terminate the recording process, kill it now!!!")
                self._process.kill()
                self._recording_thread.join(3)

        self._current_filename = None
        self._recording_thread = None
        self._process = None
        self._lines = Queue()
        self._logger.debug("FFmpegRecorder::Stop finished")

    def restart(self, timeout=0):
        self.stop(timeout)
        self.start()

    def current_filename(self):
        return self._current_filename

    def is_running(self):
        return self._running == True and self._process != None and self._recording_thread and self._recording_thread.is_alive()
