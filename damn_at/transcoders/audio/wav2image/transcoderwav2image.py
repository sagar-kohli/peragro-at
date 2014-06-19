import os, tempfile
import mimetypes, subprocess
import matplotlib.pyplot as plt

from damn_at import logger
from damn_at.transcoder import TranscoderException
from damn_at.utilities import WaveData

from damn_at.pluginmanager import ITranscoder
from damn_at.options import HexColorOption, IntOption, expand_path_template

class Audio2ImageTranscoder(ITranscoder):
    options = [HexColorOption(name = 'color', description = 'Color of the plot', default = '#0000ff'),
            IntOption(name = 'samplerate', description = 'Sample Rate of the audio', default = 800)]
    
    convert_map = {"audio/x-wav" : {"image/png" : options},
            "audio/mpeg" : {"image/png" : options},
            "audio/x-wav" : {"image/jpeg" : options},
            "audio/mpeg" : {"image/jpeg" : options}}

    def __init__(self):
        ITranscoder.__init__(self)

    def activate(self):
        pass

    def transcode(self, dest_path, file_descr, asset_id, target_mimetype,
            **options):

        #options['color']="".join(options['color'])
        file_path = expand_path_template(target_mimetype.template,
                target_mimetype.mimetype, asset_id, **options)
        
        audio_mimetype = mimetypes.guess_type(file_descr.file.filename)[0]
        try:
            tmp = tempfile.NamedTemporaryFile()
            pro = subprocess.Popen(["sox", file_descr.file.filename, "-t", "wav", "-r", str(options['samplerate']),  tmp.name], 
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, err = pro.communicate()
            if pro.returncode != 0:
                print("Sox failed %s with error code %d!" %(file_decrs.file.filename, pro.returncode), 
                        out, err)
                return False
            else:
                toopen = tmp.name
        except OSError:
            print("Sox failed %s!" %(file_descr.file.filename), out, err)
            return False

        wavedata = WaveData()
        wavedata.extractData(toopen, 2)
        channels = wavedata.getData()
        gcolor = options['color']

        plt.figure(1)
        if wavedata.nchannels == 2:
            plt.subplot(211)
            plt.plot(channels[0], color = gcolor)
            plt.axis('off')
            plt.subplot(212)
            plt.plot(channels[1], color = gcolor)
        else:
            plt.plot(channels[0])
        
        plt.axis('off')
        
        full_path = os.path.join(dest_path, file_path)
        if not os.path.exists(os.path.dirname(full_path)):
            os.makedirs(os.path.dirname(full_path))

        plt.savefig(full_path)

        return [file_path]
