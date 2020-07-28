#! /usr/bin/python3

import os
import sys
import argparse
import numpy as np
import scipy.signal as signal
import scipy.io.wavfile as wavefile
import scipy.fftpack as fftpack
import matplotlib.pyplot as plt

eps = 0.0000000001 # used to avoid zero division error

class WavGenerator:
    @staticmethod
    def generateSine(param_dict):
        time = np.arange(0, float(param_dict['duration']), 1.0/float(param_dict['sample_rate']), dtype=np.float32)
        data = float(param_dict['amp']) * np.sin(2 * np.pi * float(param_dict['freq']) * time + float(param_dict['phase']))
        return np.reshape(np.repeat(data, int(param_dict['channel'])),[len(data), int(param_dict['channel'])])

    @staticmethod
    def generateCosine(param_dict):
        time = np.arange(0, float(param_dict['duration']), 1.0/float(param_dict['sample_rate']), dtype=np.float32)
        data = float(param_dict['amp']) * np.cos(2 * np.pi * float(param_dict['freq']) * time + float(param_dict['phase']))
        return np.reshape(np.repeat(data, int(param_dict['channel'])),[len(data), int(param_dict['channel'])])

    @staticmethod
    def generateRandom(param_dict):
        wave_size = int(float(param_dict['duration']) * float(param_dict['sample_rate']))
        data = np.random.normal(float(param_dict['freq']), float(param_dict['phase']), wave_size)
        maxnum = abs(np.max(data))
        if abs(np.max(data)) < abs(np.min(data)):
            maxnum = abs(np.min(data))
        data = float(param_dict['amp']) / maxnum * data
        return np.reshape(np.repeat(data, int(param_dict['channel'])),[len(data), int(param_dict['channel'])])

    @staticmethod
    def generateWOV(param_dict):
        # leave 5 zeros for boundary detecting
        wave_size = 8000 + int((float(param_dict['duration1']) + float(param_dict['duration2'])) * float(param_dict['sample_rate']))
        sine_param2 = {
            'amp':param_dict['amp2'],
            'freq': param_dict['freq2'],
            'phase': "0.",
            'sample_rate': param_dict['sample_rate'],
            'channel': param_dict['channel'],
            'duration': param_dict['duration2']
        }
        sine_data2 = WavGenerator.generateSine(sine_param2)
        data = np.zeros((wave_size, int(param_dict['channel'])))
        data[:][data.shape[0] - sine_data2.shape[0]:data.shape[0]] = sine_data2
        if param_dict['type'] == 'wov_zeros_sine':
            return data
        sine_param1 = {
            'amp':param_dict['amp1'],
            'freq': param_dict['freq1'],
            'phase': "0.",
            'sample_rate': param_dict['sample_rate'],
            'channel': param_dict['channel'],
            'duration': param_dict['duration1']
        }
        sine_data1 = WavGenerator.generateSine(sine_param1)
        data[:][0:sine_data1.shape[0]] = sine_data1
        return data

if __name__ == "__main__":
    def parse_cmdline():
        parser = argparse.ArgumentParser(add_help=True, formatter_class=argparse.RawTextHelpFormatter,
            description='A Tool to Generate and Manipulate Wave Files.')
        parser.add_argument('-v', '--version', action='version', version='%(prog)s 1.0')
        parser.add_argument('-g', '--generate', type=str, help='generate specified types of wave\n'
        'parameter format: "wave_type; amplitude(0.0~1.0); frequency/mu; phase/sigma; sample rate; channel; format; duration"\n'
        'Note: please use float point precision, mu and sigma is used in generating white noise\n'
        'Supported wave type: sine, cosine; white_noise\n'
        'Support format: S8, S16, S32, F32\n')
        parser.add_argument('-o', '--output', type=str, help='Path to store generated files (wave, spectrum, spectrogram)', default='.')
        parser.add_argument('-p', '--preset', type=str, help='Commonly used wave presets, supported presets:\n'
        'sine_1K_10s, white_noise')
        parser.add_argument('-a', '--analysis', type=str, help='Analyze wave file, (GUI required)')
        parser.add_argument('-H', '--hb_size', type=float, help='history buffer size used used in Wake-On-Voice', default=2.1)
        parser.add_argument('-c', '--compare', type=str, help='compare recorded wave and reference wave\n'
        'parameter format: "mode;recorded_wave_path; reference_wave_path"\n'
        'Supported comparison mode: freq, binary')
        parser.add_argument('-s', '--fftsize', type=int, help='fftsize in fft transform', default=8192)
        parser.add_argument('-t', '--threshold', type=float, help='thresholds used in comparing wave file', default=-50.)
        parser.add_argument('-T', '--snr_threshold', type=float, help='Acceptable SNR threshold', default=65.)
        parser.add_argument('-w', '--window_type', type=str, help='window function used in fft transformation', default='blackman')
        return vars(parser.parse_args())

    def parse_params_and_gen_wav(cmd_param):
        supported_type = ['sine', 'cosine', 'white_noise', 'wov_sine_sine', 'wov_zeros_sine']
        param_keys = ['type', 'amp', 'freq', 'phase', 'sample_rate', 'channel', 'format', 'duration']
        param_keys_wov = ['type', 'amp1', 'freq1', 'duration1','amp2', 'freq2', 'duration2', 'sample_rate', 'channel', 'format']
        split_cmd_params = cmd_param.split(';')
        wave_params = [param.strip() for param in split_cmd_params]
        param_dict = dict(zip(param_keys, wave_params))
        if param_dict['type'] not in supported_type:
            print("Unsupported wave type")
            sys.exit(1)
        if param_dict['type'] == 'sine':
            wave_data = WavGenerator.generateSine(param_dict)
            return wave_data, param_dict
        if param_dict['type'] == 'cosine':
            wave_data = WavGenerator.generateCosine(param_dict)
            return wave_data, param_dict
        if param_dict['type'] == 'white_noise':
            wave_data = WavGenerator.generateRandom(param_dict)
            return wave_data, param_dict
        if param_dict['type'] in ['wov_sine_sine', 'wov_zeros_sine']:
            param_dict_wov = dict(zip(param_keys_wov, wave_params))
            wave_data = WavGenerator.generateWOV(param_dict_wov)
            return wave_data, param_dict_wov

    def store_wave(wave_data, wave_params, path):
        supported_format = ['S8', 'S16', 'S32', 'F32']
        wave_path = path
        if not path.endswith('wav'):
            if (wave_params['type'] in ['wov_sine_sine', 'wov_zeros_sine']):
                wave_path = path + "/" + wave_params['type'] + '.wav'
            else:
                wave_name = wave_params['type'] + wave_params['channel'] + 'ch' + wave_params['freq'] + 'Hz' + wave_params['sample_rate'] + '.wav'
                if wave_params['type'] == 'white_noise':
                    wave_name = wave_params['type'] + wave_params['channel'] + 'ch' + wave_params['freq'] + 'mean' + wave_params['phase'] + 'std' + wave_params['sample_rate'] + '.wav'
                wave_path = path + '/'  + wave_name
        wave_format = wave_params['format'].upper()
        if wave_format not in supported_format:
            print('Unsupported wave format: %s' % wave_format)
            sys.exit(1)
        if wave_format == 'S8':
            wave_data = (np.iinfo(np.int8).max * wave_data).astype(np.int8)
        if wave_format == 'S16':
            wave_data = (np.iinfo(np.int16).max * wave_data).astype(np.int16)
        if wave_format == 'S32':
            wave_data = (np.iinfo(np.int32).max * wave_data).astype(np.int32)
        try :
            wavefile.write(wave_path, int(wave_params['sample_rate']), wave_data)
        except:
            print("Path specified not valid: %s" % wave_path)

    def normalize(wave_data):
        max_elem = np.max(wave_data)
        min_elem = np.min(wave_data)
        if abs(max_elem) > abs(min_elem):
            return wave_data / (float(abs(max_elem)) + eps)
        else:
            return wave_data / (float(abs(min_elem)) + eps)

    def dump_wave_info(wave_info, freq_bin):
        if len(wave_info[0]) == 0:
            print("No peak detected")
            return
        for i in range(len(wave_info[0])):
            print("%0.3fdB peak detected at %0.3fHz" % (wave_info[1]['peak_heights'][i], freq_bin * wave_info[0][i]))

    def compare_wave_feature(ref_peaks, wave_peaks, freq_bin):
        ret = True
        if len(wave_peaks[0]) == 0:
            print("No peak detected, wave may have DC component")
            return False
        for i in range(len(wave_peaks[0])):
            if wave_peaks[0][i] not in ref_peaks[0]:
                ret = False
                print("Recorded wave introduced new frequency component:%0.3fdB @ %0.3fHz"
                    % (wave_peaks[1]['peak_heights'][i], freq_bin * wave_peaks[0][i]))
            else:
                print("%0.3fdB peak detected at %0.3fHz" % (wave_peaks[1]['peak_heights'][i], freq_bin * wave_peaks[0][i]))
        return ret

    def calc_snr(ref_spectrum, wave_spectrum):
        signal_power = np.sum(2 * np.square(ref_spectrum)) # bilateral spectrum
        noise = wave_spectrum - ref_spectrum
        noise_power = np.sum(2 * np.square(noise))
        return 10 * np.log10(signal_power / (noise_power + eps))

    # float point binary comparison is not supported, and will not be supported
    def compare_wav_bin(wave_path, ref_path):
        fs_wav, wave = wavefile.read(wav_path)
        fs_ref, ref_wav = wavefile.read(ref_path)
        if fs_wav != fs_ref:
            print('Can not compare wave with different sample rate')
            sys.exit(1)
        compare_result = np.array_equal(ref_wav, wave)
        if compare_result:
            print('Recorded wave is binary same as reference wave')
            print("Wave comparison result: PASSED")
        else:
            print('Recorded wave is not binary same as reference wave')
            print("Wave comparison result: FAILED")

    # remove zeros in two sides
    def trim_wave(wave):
        wave_mono = wave[:,0]
        left_idx = 0
        right_idx = wave_mono.shape[0] - 1
        while True:
            if abs(wave_mono[left_idx]) > 100:
                break
            left_idx = left_idx + 1
        while True:
            if abs(wave_mono[right_idx]) > 100:
                break
            right_idx = right_idx - 1
        return wave[left_idx:right_idx,:], left_idx

    # float point binary comparison is not supported, and will not be supported
    def compare_wav_dsm(wave_path, ref_path):
        fs_wav, wave = wavefile.read(wav_path)
        fs_ref, ref_wav = wavefile.read(ref_path)
        if fs_wav != fs_ref:
            print('Can not compare wave with different sample rate')
            sys.exit(1)
        trimed_ref_wave, _ = trim_wave(ref_wav)
        # compare the first two channel
        trimed_wave_ch_0_1, delay1 = trim_wave(wave[:,0:2])
        trimed_ref_wave = trimed_ref_wave[0:trimed_wave_ch_0_1.shape[0],:]
        compare_result0_1 = np.array_equal(trimed_ref_wave, trimed_wave_ch_0_1)
        # compare the second two channel
        trimed_wave_ch_2_3, delay2 = trim_wave(wave[:,2:4])
        trimed_ref_wave = trimed_ref_wave[0:trimed_wave_ch_2_3.shape[0],:]
        compare_result2_3 = np.array_equal(trimed_ref_wave, trimed_wave_ch_2_3)

        dsm_delay = ((delay2 - delay1) / 48000 * 1000)
        print("DSM delay is %0.3fms" % dsm_delay)
        if compare_result0_1 and compare_result2_3 and dsm_delay < 5.:
            print('Recorded wave is binary same as reference wave')
            print("Wave comparison result: PASSED")
        else:
            print('Recorded wave is not binary same as reference wave')
            print("Wave comparison result: FAILED")

    def compare_wav_freq(wave_path, ref_path, fftsize, threshold, snr_threhold, window_type):
        fs_wav, wave = wavefile.read(wav_path)
        fs_ref, ref_wav = wavefile.read(ref_path)
        if fs_wav != fs_ref:
            print("Sample rate of recorded wave and reference wave is not the same")
            sys.exit(1)
        if ref_wav.shape[0] < 3 * fs_wav:
            print("Reference wave data should be longer than 3 second")
            sys.exit(1)
        if wave.shape[0] < 3 * fs_wav:
            print("Wave data should be longer than 3 second")
            sys.exit(1)

        # Generally, reference wave of all channels should be the same, only analyze
        # the first channel.
        ref_mono = ref_wav[:, 0]
        ref_spectrum = normalize(abs(fftpack.fft(signal.get_window(window_type, fftsize) * ref_mono[0: 0 + fftsize], fftsize)[0:fftsize//2]))
        ref_spectrum_log = 20 * np.log10(ref_spectrum)
        ref_peaks = signal.find_peaks(ref_spectrum_log, height=threshold)
        print("Analyze reference wave:" )
        dump_wave_info(ref_peaks, fs_ref / fftsize)

        analysis_point = [0, (wave.shape[0] - fftsize) // 2 , wave.shape[0] - fftsize]
        compare_result = []
        chan_snr = []
        for chan in range(wave.shape[1]):
            wave_mono = normalize(wave[:,chan])
            snr_list = []
            for ana_point in analysis_point:
                print("Analyze wave at [%d:%d] in channel %d" %(ana_point, ana_point + fftsize, chan))
                wave_mono_spectrum = normalize(abs(fftpack.fft(signal.get_window(window_type, fftsize) * wave_mono[ana_point:ana_point+fftsize], fftsize)[0:fftsize//2]))
                wave_spectrum_log = 20 * np.log10(wave_mono_spectrum)
                wave_peaks = signal.find_peaks(wave_spectrum_log, height=threshold)
                snr = calc_snr(ref_spectrum, wave_mono_spectrum)
                print("Signal-to-Noise Ratio: %0.3fdB" % snr)
                snr_list.append(snr)
                compare_result.append(compare_wave_feature(ref_peaks, wave_peaks, fs_wav / fftsize))
            snr_mean = np.mean(np.array(snr_list))
            print("==== SNR in Channel %d: %0.3fdB ====" % (chan, snr_mean))
            chan_snr.append(snr_mean)
        snr_pass = [snr > snr_threhold for snr in chan_snr]
        if all(compare_result) and all(snr_pass):
            print("Wave comparison result: PASSED")
        else:
            print("Wave comparison result: FAILED")

    def find_zero_range(wave, start, backward=False):
        step = 100
        if backward:
            step = -step
        win = 100 * np.ones(abs(step), dtype=wave.dtype)
        while not np.all(np.abs(wave[start:start + abs(step)]) < win):
            start = start + step
        end = start
        while np.all(np.abs(wave[start:start + abs(step)]) < win) and start > 0:
            start = start - 1
        while np.all(np.abs(wave[end:end + abs(step)]) < win) and end < wave.shape[0]:
            end = end + 1
        return start,end + abs(step) - 1

    def calc_spectrum(wave, fftsize, window_type, threshold):
        windowed_signal = signal.get_window(window_type, fftsize) * wave
        wave_spectrum = normalize(abs(fftpack.fft(windowed_signal, fftsize))[0: fftsize//2])
        wave_spectrum_log = 20 * np.log10(wave_spectrum)
        peaks = signal.find_peaks(wave_spectrum_log, height=threshold)
        return wave_spectrum_log, peaks

    def calc_ref_wave_params(wave, fs_ref, **cmd_args):
        fftsize = cmd_args['fftsize']
        zero_start, zero_end = find_zero_range(wave, 0)
        # calculate frequency of low volume sine wave

        lfft_start = (zero_start - fftsize) // 2
        lspectrum, low_vol_sine_peak = calc_spectrum(wave[lfft_start: lfft_start + fftsize], fftsize, cmd_args['window_type'], cmd_args['threshold'])
        low_sine_freq = low_vol_sine_peak[0][0] / fftsize * fs_ref if len(low_vol_sine_peak[0] == 1) else 0.
        # calculate frequency of high volume sine wave
        hfft_start = zero_end + (wave.shape[0] - fftsize - zero_end) // 2
        hspectrum, high_vol_sine_peak = calc_spectrum(wave[hfft_start: hfft_start + fftsize], fftsize, cmd_args['window_type'], cmd_args['threshold'])
        high_sine_freq = low_vol_sine_peak[0][0] / fftsize * fs_ref if len(high_vol_sine_peak[0] == 1) else 0.
        return zero_start, zero_end, low_sine_freq, high_sine_freq

    def calc_wov_wav_params(wave, fs_wav, **cmd_args):
        fftsize = cmd_args['fftsize']
        start_search_point = int(fs_wav * cmd_args['hb_size'])
        zero_start, zero_end = find_zero_range(wave, start_search_point, backward=True)
        lfft_start = (zero_start - fftsize) // 2
        lspectrum, low_vol_sine_peak = calc_spectrum(wave[lfft_start: lfft_start + fftsize], fftsize, cmd_args['window_type'], cmd_args['threshold'])
        low_sine_freq = low_vol_sine_peak[0][0] / fftsize * fs_wav if len(low_vol_sine_peak[0] == 1) else 0.
        # calculate frequency of high volume sine wave
        hfft_start = zero_end + (wave.shape[0] - fftsize - zero_end) // 2
        hspectrum, high_vol_sine_peak = calc_spectrum(wave[hfft_start: hfft_start + fftsize], fftsize, cmd_args['window_type'], cmd_args['threshold'])
        high_sine_freq = low_vol_sine_peak[0][0] / fftsize * fs_wav if len(high_vol_sine_peak[0] == 1) else 0.
        return zero_start, zero_end, low_sine_freq, high_sine_freq

    def print_wov_wave_param(params, wave_length, fs):
        print('Low volume sine wave duration: %0.5fs ~ %0.3fs' % (0., (params[0] - 1) / fs))
        print('Low volume sine wave frequency: %0.2f Hz' % params[2])
        print('High volume sine wave duration: %0.5fs ~ %0.3fs' % (params[1] / fs, wave_length / fs))
        print('High volume sine wave frequency: %0.2f Hz' % (params[3]))

    def compare_wav_wov(wav_path, ref_path, **cmd_args):
        hb_size = cmd_args['hb_size']
        fftsize = cmd_args['fftsize']
        window_type = cmd_args['window_type']
        fs_wav, wave = wavefile.read(wav_path)
        fs_ref, ref_wav = wavefile.read(ref_path)
        trimed_wave, _ = trim_wave(wave)
        if fs_wav != fs_ref:
            print('Can not compare wave with different sample rate')
            sys.exit(1)
        ref_wave_params = calc_ref_wave_params(ref_wav[:,1], fs_ref, **cmd_args)
        print_wov_wave_param(ref_wave_params, ref_wav.shape[0], fs_ref)
        wave_params = calc_wov_wav_params(trimed_wave[:,1], fs_wav, **cmd_args)
        print_wov_wave_param(wave_params, trimed_wave.shape[0], fs_ref)

    cmd_args = parse_cmdline()

    if cmd_args['generate'] is not None:
        wave_data, wave_params = parse_params_and_gen_wav(cmd_args['generate'].strip())
        store_wave(wave_data, wave_params, cmd_args['output'].strip())

    if cmd_args['preset'] is not None:
        wave_presets = {
            "sine_1K_10s": "sine;1.0;1000;0.;48000;2;S16;10",
            "white_noise": "white_noise;1.0;0.0;0.2;48000;2;S16;10",
            # type;amp1;freq1;duration1;amp2;freq2;duration2;sample_rate;channels;format;
            "wov_sine_sine": "wov_sine_sine;0.3;1000;4;1.0;1000;6;48000;2;S16",
            # parameters for the first sine take no effect
            "wov_zeros_sine": "wov_zeros_sine;0.3;1000;4;1.0;1000;6;48000;2;S16"
        }
        req_preset = cmd_args['preset'].strip()
        if req_preset not in wave_presets.keys():
            print("Preset not found")
            sys.exit(1)
        wave_data, wave_params = parse_params_and_gen_wav(wave_presets[req_preset])
        store_wave(wave_data, wave_params, cmd_args['output'].strip())

    if cmd_args['analysis'] is not None:
        pass

    if cmd_args['compare'] is not None:
        supported_mode = ['freq', 'binary', 'dsm', 'wov']
        cmd_line = cmd_args['compare'].strip().split(';')
        comparison_mode = cmd_line[0].strip()
        if comparison_mode not in supported_mode:
            print("Unsupported comparison mode: %s" % comparison_mode)
            print('Supported comparison modes are: ' + str(supported_mode))
            sys.exit(1)
        wav_path, ref_path = [path.strip() for path in cmd_line[1:]]
        if not os.path.exists(wav_path):
            print('Recorded wave path not exist: %s' % wav_path)
            sys.exit(1)
        if not os.path.exists(ref_path):
            print('Reference wave path not exist: %s' % ref_path)
            sys.exit(1)
        if comparison_mode == 'freq':
            compare_wav_freq(wav_path, ref_path, cmd_args['fftsize'], cmd_args['threshold'], cmd_args['snr_threshold'], cmd_args['window_type'])
        if comparison_mode == 'binary':
            compare_wav_bin(wav_path, ref_path)
        if comparison_mode == 'dsm':
            compare_wav_dsm(wav_path, ref_path)
        if comparison_mode == 'wov':
            compare_wav_wov(wav_path, ref_path, **cmd_args)
