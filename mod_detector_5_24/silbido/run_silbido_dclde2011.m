function run_silbido_dclde2011(run_deepwhistle)
% run_silbido_dclde2011  Silbido baseline on the DCLDE 2011 test files of Li et al. (2023) for the detector paper.
%
% Put this file in an empty folder, make it MATLAB's current folder and type
%     >> run_silbido_dclde2011
% Needs MATLAB R2019b or newer with the Signal Processing and Image Processing Toolboxes, an internet connection and
% ~1.5 GB of disk. It
%   1. downloads Silbido 3.0 and the 12 test recordings (~1.1 GB) from NOAA's public DCLDE 2011 bucket and checks them;
%   2. runs Silbido's classic graph-search whistle detector (Roch et al. 2011) on each recording with Silbido's
%      default odontocete settings (5-50 kHz, 8 ms frames every 2 ms, 10 dB peaks, whistles >= 150 ms);
%   3. writes silbido_detections.zip (detections + log) in this folder. Send that zip back.
% Safe to re-run: verified downloads and finished recordings are skipped.
%
% run_silbido_dclde2011(true) also runs Silbido's DeepWhistle peak detector (Li et al. 2020) + graph search; this
% needs the Deep Learning Toolbox and its "Deep Learning Toolbox Converter for ONNX Model Format" support package.
%
% Data: Roch et al. (2025) DCLDE 2011 Conference Data, doi:10.25921/wsnc-js16. Silbido: Roch et al. (2011) JASA
% 130(4) 2212-2223, github.com/MarineBioAcousticsRC/silbido.

if nargin < 1
    run_deepwhistle = false;
end
WORK = pwd;
NOAA = 'https://storage.googleapis.com/noaa-passive-bioacoustic/dclde/2011/dclde_2011/';
DATA = fullfile(WORK, 'dclde2011');
OUT = fullfile(WORK, 'dclde2011_detections');
SILBIDO = fullfile(WORK, 'silbido-3.0');
LOG = fullfile(OUT, 'silbido_run_log.txt');

% species, file stem, wav size (bytes), wav MD5 (the files of mod_detector_5_24/colab_download_dclde2011.py)
FILES = {
    'bottlenose',   'Qx-Tt-SCI0608-N1-060814-121518',          145859024, '016bde125be1e6a9c31bbf8731ba234b'
    'bottlenose',   'palmyra092007FS192-070924-205305',         95821868, 'c7de7f784e6e97d6683a97634914ba61'
    'bottlenose',   'palmyra092007FS192-070924-205730',         57385004, '5913fa93ade7ffd494de84c9efde6d8b'
    'common',       'Qx-Dc-CC0411-TAT11-CH2-041114-154040-s',  115200044, 'e4380e4e3809a42743800d6bb89456a8'
    'common',       'QX-Dc-FLIP0610-VLA-061015-165000',        115200044, '1cf400d3e834f8e9bbadf1e9afbc2b06'
    'common',       'Qx-Dc-SC03-TAT09-060516-171606',           89835564, '3fcb59129285fe4a1afdd234c21b9e3c'
    'melon-headed', 'palmyra092007FS192-071004-032342',         76161068, '002bb860f8bbe07dab66fa2ffcb2c6da'
    'melon-headed', 'palmyra102006-061020-204327_4',            25034796, '1d18c137211b6bbb450747bdef77443f'
    'melon-headed', 'palmyra092007FS192-070925-023000',        160201004, '0cdead90218710396f7a419487988bb3'
    'spinner',      'palmyra092007FS192-070927-224737',         54794540, '1785cc925537ad78fb10bc6cf8018cfd'
    'spinner',      'palmyra102006-061103-213127_4',            60522540, '50595518e6a39e42d05a68809d5edb16'
    'spinner',      'palmyra092007FS192-071011-232000',         48215852, '0b34faa434be823eccdc64462d9c3df1'
    };

% ---------------------------------------------------------------- checks before downloading anything
need ={'signal', 'Signal Processing Toolbox'; 'images', 'Image Processing Toolbox'};
for i = 1:size(need, 1)
    if isempty(ver(need{i, 1}))
        error('Silbido needs the %s, which is not installed.', need{i, 2});
    end
end
heap_mb = java.lang.Runtime.getRuntime.maxMemory / 2^20;
if heap_mb < 1000
    error(['Silbido needs at least 1 GB of Java heap memory (now %.0f MB). Set it under Preferences > General > ' ...
        'Java Heap Memory (2048 MB is good), restart MATLAB and run this again.'], heap_mb);
end

% ---------------------------------------------------------------- Silbido 3.0
silbido_zip = fullfile(WORK, 'silbido-3.0.zip');
fetch([NOAA 'software/silbido-3.0.zip'], silbido_zip, 29724096, 'daa1504e634a8e71411e6a0e540bab50');
if ~isfile(fullfile(SILBIDO, 'silbido_init.m'))
    unzip(silbido_zip, SILBIDO);
end
addpath(SILBIDO);
silbido_init;   % adds Silbido's MATLAB and Java paths

% Silbido's default odontocete parameters (matlab/lib/odontocete_deep.xml), given as a struct so that the XML reader,
% a compiled file shipped only for Windows, is not needed. Where that reader works, the values are checked against it.
P = struct('advance_ms', 2, 'length_ms', 8, 'maxgap_Hz', 1000, 'low_cutoff_Hz', 5000, 'high_cutoff_Hz', 50000, ...
    'peak_method', 'Energy', 'confidence_thresh', 0.5, 'energy_thresh', 10, 'minlen_ms', 150, 'maxgap_ms', 50, ...
    'activeset_s', 0.050, 'blocklen_s', 3, 'click_dB', 10, 'broadband', 0.01, 'predict_lookback_s', 0.025, ...
    'disambiguate_s', 0.3);
if exist('tinyxml2_wrap') == 3 %#ok<EXIST>
    X = dtThresh('odontocete_deep.xml');
    fx = setdiff(fieldnames(X), {'peak_method'});
    fp = setdiff(fieldnames(P), {'peak_method'});
    if ~isempty(setxor(fx, fp))
        error('parameter names differ from odontocete_deep.xml: %s', strjoin(setxor(fx, fp), ', '));
    end
    for i = 1:numel(fx)
        if double(X.(fx{i})) ~= P.(fx{i})
            error('parameter %s differs from odontocete_deep.xml', fx{i});
        end
    end
    fprintf('parameters match Silbido''s odontocete_deep.xml\n');
end

% classic graph search: energy peaks (PeakMethod Energy; Silbido 3.0 otherwise defaults to DeepWhistle)
runs = struct('tag', 'silbido-graph', 'args', {{'ParameterSet', P, 'PeakMethod', 'Energy', 'Noise', 'median'}});
if run_deepwhistle
    Pd = P;
    Pd.peak_method = 'DeepWhistle';
    runs(end + 1) = struct('tag', 'silbido-deepwhistle', 'args', {{'ParameterSet', Pd}});
end

% ---------------------------------------------------------------- recordings
for i = 1:size(FILES, 1)
    fetch(sprintf('%sdevelopment/%s/%s.wav', NOAA, FILES{i, 1}, FILES{i, 2}), ...
        fullfile(DATA, 'development', FILES{i, 1}, [FILES{i, 2} '.wav']), FILES{i, 3}, FILES{i, 4});
end

% ---------------------------------------------------------------- detection
if ~isfolder(OUT)
    mkdir(OUT);
end
logf = fopen(LOG, 'a');
closer = onCleanup(@() fclose(logf));
say(logf, '==== %s  MATLAB %s  %s  Java heap %.0f MB', datestr(now, 31), version, computer, heap_mb);
say(logf, 'Silbido 3.0 (NOAA silbido-3.0.zip, MD5 daa1504e634a8e71411e6a0e540bab50)');
say(logf, 'parameters: %s', jsonencode(P));
for r = 1:numel(runs)
    say(logf, 'run %s: dtTonalsTracking(wav, 0, Inf, %s)', runs(r).tag, describe(runs(r).args));
    for i = 1:size(FILES, 1)
        wav = fullfile(DATA, 'development', FILES{i, 1}, [FILES{i, 2} '.wav']);
        out = fullfile(OUT, runs(r).tag, FILES{i, 1}, [FILES{i, 2} '.det']);
        if isfile(out)
            say(logf, '  %-13s %s: already done', FILES{i, 1}, FILES{i, 2});
            continue
        end
        t0 = tic;
        tonals = dtTonalsTracking(wav, 0, Inf, runs(r).args{:});
        if ~isfolder(fileparts(out))
            mkdir(fileparts(out));
        end
        dtTonalsSave([out '.part'], tonals);
        movefile([out '.part'], out);
        say(logf, '  %-13s %s: %d tonals in %.0f s', FILES{i, 1}, FILES{i, 2}, tonals.size(), toc(t0));
    end
end

% ---------------------------------------------------------------- result to send back
clear closer   % closes the log so the zip gets all of it
zipname = fullfile(WORK, 'silbido_detections.zip');
zip(zipname, [{runs.tag}, {'silbido_run_log.txt'}], OUT);
fprintf('\nDONE. Send this file back: %s\n', zipname);
end


function fetch(url, dest, nbytes, md5)
% Download url to dest unless dest already has the right size; verify size and MD5 before keeping it.
if isfile(dest)
    d = dir(dest);
    if d.bytes == nbytes
        return
    end
end
folder = fileparts(dest);
if ~isfolder(folder)
    mkdir(folder);
end
tmp = [dest '.part'];
opts = weboptions('Timeout', 600);
for attempt = 1:3
    try
        tmp = websave(tmp, url, opts);
        d = dir(tmp);
        if d.bytes == nbytes && strcmp(md5file(tmp), md5)
            movefile(tmp, dest);
            fprintf('downloaded %s\n', dest);
            return
        end
        fprintf('%s: size or checksum mismatch (attempt %d)\n', url, attempt);
    catch e
        fprintf('%s: %s (attempt %d)\n', url, e.message, attempt);
    end
    pause(5);
end
error('could not download %s; run the script again later', url);
end


function h = md5file(p)
md = java.security.MessageDigest.getInstance('MD5');
fid = fopen(p, 'r');
c = onCleanup(@() fclose(fid));
while true
    b = fread(fid, 2^24, '*uint8');
    if isempty(b)
        break
    end
    md.update(typecast(b, 'int8'));
end
h = lower(reshape(dec2hex(typecast(md.digest(), 'uint8'))', 1, []));
end


function s = describe(args)
% keyword/value arguments as text for the log (structs shown as "<parameters>")
parts = cell(1, numel(args));
for k = 1:numel(args)
    if ischar(args{k})
        parts{k} = ['''' args{k} ''''];
    else
        parts{k} = '<parameters>';
    end
end
s = strjoin(parts, ', ');
end


function say(logf, varargin)
msg = sprintf(varargin{:});
fprintf('%s\n', msg);
fprintf(logf, '%s\n', msg);
end
