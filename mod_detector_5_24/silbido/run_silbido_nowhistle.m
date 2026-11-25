function run_silbido_nowhistle(run_extras)
% run_silbido_nowhistle  Silbido on the no-whistle test recordings (beaked and sperm whales, 2017) for the detector
% paper, plus two extra detection thresholds on these and on the DCLDE 2011 test recordings.
%
% Put this file in a folder together with the downloaded nowhistle_wav folder (or its unzipped parts: the script
% looks for the WAV files in every subfolder), make that folder MATLAB's current folder and type
%     >> run_silbido_nowhistle
% If last time's folder (run_silbido_dclde2011) still exists, use that one: Silbido and the DCLDE 2011 recordings in
% it are reused instead of downloaded again.
% Needs MATLAB R2019b or newer with the Signal Processing and Image Processing Toolboxes, an internet connection and
% ~5 GB of disk (3.4 GB of WAV files, 1.1 GB of DCLDE 2011 recordings). It
%   1. downloads Silbido 3.0 (the same zip as last time) from NOAA's public DCLDE 2011 bucket and checks it;
%   2. checks the 146 WAV files against nowhistle_wav_manifest.csv (size and MD5) and stops if any is missing or broken;
%   3. MAIN RUN: Silbido's classic graph search with its default odontocete settings (exactly as on DCLDE 2011 on
%      5 Nov 2026: 5-50 kHz, 8 ms frames every 2 ms, 10 dB peaks, whistles >= 150 ms) on the 146 files;
%   4. EXTRA RUNS (skipped with run_silbido_nowhistle(false)): the same once more on the 12 DCLDE 2011 recordings
%      (should repeat the 5 Nov result exactly), then peak thresholds of 8 dB and 12 dB instead of 10 dB on both sets;
%   5. writes silbido_nowhistle_detections.zip (detections + log) in this folder, after step 3 and again at the end.
%      Send that zip back.
% Safe to re-run: verified downloads and finished recordings are skipped.
%
% Data: no-whistle recordings: NOAA/SWFSC 2017 survey (DCLDE 2022, 1705 array), channel 0 resampled to 192 kHz by
% mod_detector_5_24/colab_silbido_audio.py; DCLDE 2011: Roch et al. (2025), doi:10.25921/wsnc-js16.
% Silbido: Roch et al. (2011) JASA 130(4) 2212-2223, github.com/MarineBioAcousticsRC/silbido.

if nargin < 1
    run_extras = true;
end
WORK = pwd;
NOAA = 'https://storage.googleapis.com/noaa-passive-bioacoustic/dclde/2011/dclde_2011/';
DATA = fullfile(WORK, 'dclde2011');
OUT = fullfile(WORK, 'silbido_nowhistle_output');
SILBIDO = fullfile(WORK, 'silbido-3.0');
MANIFEST = 'nowhistle_wav_manifest.csv';
ZIPNAME = fullfile(WORK, 'silbido_nowhistle_detections.zip');
LOG = fullfile(OUT, 'silbido_nowhistle_log.txt');

% species, file stem, wav size (bytes), wav MD5 (the files of mod_detector_5_24/colab_download_dclde2011.py)
DCLDE = {
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
need = {'signal', 'Signal Processing Toolbox'; 'images', 'Image Processing Toolbox'};
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
if ~isfolder(OUT)
    mkdir(OUT);
end

% ---------------------------------------------------------------- the no-whistle WAV files
fprintf('looking for %s and the WAV files in %s and its subfolders...\n', MANIFEST, WORK);
found = dir(fullfile(WORK, '**', MANIFEST));
found = found(~startsWith({found.name}, '._'));
if isempty(found)
    error(['%s not found. Download the nowhistle_wav folder from the shared Google Drive folder into %s ' ...
        '(unzip it there if it came as zip files) and run this again.'], MANIFEST, WORK);
end
mpath = fullfile(found(1).folder, found(1).name);
manifest_md5 = md5file(mpath);
for k = 2:numel(found)
    if ~strcmp(md5file(fullfile(found(k).folder, found(k).name)), manifest_md5)
        error('two different copies of %s were found (%s, %s); keep only the newest download.', MANIFEST, ...
            found(1).folder, found(k).folder);
    end
end
M = read_manifest(mpath);
fprintf('%s: %d files\n', MANIFEST, numel(M.wav_file));

wavs = dir(fullfile(WORK, '**', '*.wav'));
wavs = wavs(~startsWith({wavs.name}, '._'));   % skip macOS "._" helper files
paths = cell(numel(M.wav_file), 1);
missing = {};
fprintf('checking the size and MD5 of %d WAV files (about a minute)...\n', numel(M.wav_file));
for i = 1:numel(M.wav_file)
    cand = wavs(strcmp({wavs.name}, M.wav_file{i}) & [wavs.bytes] == M.size_bytes(i));
    for c = 1:numel(cand)
        p = fullfile(cand(c).folder, cand(c).name);
        if strcmp(md5file(p), M.md5{i})
            paths{i} = p;
            break
        end
    end
    if isempty(paths{i})
        missing{end + 1} = M.wav_file{i}; %#ok<AGROW>
    end
end
if ~isempty(missing)
    error(['%d of %d WAV files are missing or damaged, for example %s. Download the nowhistle_wav folder again ' ...
        '(all its zip parts), unzip everything inside %s and run this again.'], numel(missing), ...
        numel(M.wav_file), strjoin(missing(1:min(3, end)), ', '), WORK);
end
fprintf('all %d WAV files present and correct\n', numel(paths));

% ---------------------------------------------------------------- Silbido 3.0 (the same zip as on 5 Nov 2026)
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
% The run always uses P (the values of the 5 Nov run); this comparison is only recorded in the log, so that a problem
% with the XML reader on this computer cannot stop the run.
xml_note = 'XML reader not available here (not compared)';
if exist('tinyxml2_wrap') == 3 %#ok<EXIST>
    try
        X = dtThresh('odontocete_deep.xml');
        fx = setdiff(fieldnames(X), {'peak_method'});
        fp = setdiff(fieldnames(P), {'peak_method'});
        diffs = setxor(fx, fp);
        for i = 1:numel(fx)
            if isfield(P, fx{i}) && double(X.(fx{i})) ~= P.(fx{i})
                diffs{end + 1} = fx{i}; %#ok<AGROW>
            end
        end
        if isempty(diffs)
            xml_note = 'parameters match Silbido''s odontocete_deep.xml';
        else
            xml_note = ['NOTE: differs from odontocete_deep.xml in: ' strjoin(diffs, ', ')];
        end
    catch e
        xml_note = ['XML reader failed (not compared): ' e.message];
    end
end
% classic graph search with energy peaks, as on 5 Nov; the extra runs change only the peak threshold (energy_thresh,
% which Silbido's TonalTracker uses as its peak threshold for PeakMethod Energy)
tags = {'silbido-graph', 'silbido-graph-thr8', 'silbido-graph-thr12'};
thresholds = [10, 8, 12];

say(LOG, '==== %s  MATLAB %s  %s  Java heap %.0f MB', datestr(now, 31), version, computer, heap_mb);
say(LOG, 'Silbido 3.0 (NOAA silbido-3.0.zip, MD5 daa1504e634a8e71411e6a0e540bab50); %s', xml_note);
say(LOG, 'no-whistle manifest %s: %d files, MD5 %s', MANIFEST, numel(M.wav_file), manifest_md5);
copyfile(mpath, fullfile(OUT, MANIFEST));

% ---------------------------------------------------------------- 3. main run: no-whistle files, default settings
nw = [M.wav_file, paths];
run_set(LOG, OUT, 'nowhistle', tags{1}, setfield(P, 'energy_thresh', thresholds(1)), nw); %#ok<SFLD>
make_zip(ZIPNAME, OUT, MANIFEST, LOG);
fprintf('\nMAIN RUN DONE. %s is ready (it is updated again at the end).\n\n', ZIPNAME);

% ---------------------------------------------------------------- 4. extra runs
if run_extras
    dc = cell(size(DCLDE, 1), 2);
    for i = 1:size(DCLDE, 1)
        wav = fullfile(DATA, 'development', DCLDE{i, 1}, [DCLDE{i, 2} '.wav']);
        fetch(sprintf('%sdevelopment/%s/%s.wav', NOAA, DCLDE{i, 1}, DCLDE{i, 2}), wav, DCLDE{i, 3}, DCLDE{i, 4});
        dc(i, :) = {[DCLDE{i, 1} '/' DCLDE{i, 2}], wav};
    end
    run_set(LOG, OUT, 'dclde2011', tags{1}, setfield(P, 'energy_thresh', thresholds(1)), dc); %#ok<SFLD>
    for t = 2:numel(tags)
        Pt = setfield(P, 'energy_thresh', thresholds(t)); %#ok<SFLD>
        run_set(LOG, OUT, 'nowhistle', tags{t}, Pt, nw);
        run_set(LOG, OUT, 'dclde2011', tags{t}, Pt, dc);
    end
    make_zip(ZIPNAME, OUT, MANIFEST, LOG);
end
fprintf('\nDONE. Send this file back: %s\n', ZIPNAME);
end


function run_set(LOG, OUT, set_name, tag, P, files)
% Silbido on each file of one set with one parameter struct; skips files whose .det already exists.
args = {'ParameterSet', P, 'PeakMethod', 'Energy', 'Noise', 'median'};
say(LOG, 'run %s on %s (%d files): dtTonalsTracking(wav, 0, Inf, %s)', tag, set_name, size(files, 1), describe(args));
say(LOG, 'parameters: %s', jsonencode(P));
for i = 1:size(files, 1)
    [sub, stem] = fileparts(files{i, 1});
    out = fullfile(OUT, set_name, tag, sub, [stem '.det']);
    if isfile(out)
        say(LOG, '  %s: already done', files{i, 1});
        continue
    end
    t0 = tic;
    tonals = dtTonalsTracking(files{i, 2}, 0, Inf, args{:});
    if ~isfolder(fileparts(out))
        mkdir(fileparts(out));
    end
    dtTonalsSave([out '.part'], tonals);
    movefile([out '.part'], out);
    say(LOG, '  [%d/%d] %s: %d tonals in %.0f s', i, size(files, 1), files{i, 1}, tonals.size(), toc(t0));
end
end


function make_zip(zipname, OUT, MANIFEST, LOG)
% detections, log and the manifest that was used; only what exists so far
items = {'nowhistle', 'dclde2011', 'silbido_nowhistle_log.txt', MANIFEST};
items = items(cellfun(@(f) exist(fullfile(OUT, f), 'file') > 0, items));
say(LOG, 'zip %s', zipname);
zip(zipname, items, OUT);
end


function M = read_manifest(p)
expected = 'wav_file,source_flac,group,encounter_id,n_samples,duration_s,size_bytes,md5';
fid = fopen(p, 'r');
c = onCleanup(@() fclose(fid));
head = strtrim(fgetl(fid));
if ~strcmp(head, expected)
    error('%s has an unexpected header: %s', p, head);
end
C = textscan(fid, '%s %s %s %s %f %f %f %s', 'Delimiter', ',', 'Whitespace', '');   % group names contain spaces
M = struct('wav_file', {C{1}}, 'size_bytes', C{7}, 'md5', {C{8}});
if isempty(M.wav_file) || numel(unique(M.wav_file)) ~= numel(M.wav_file)
    error('%s is empty or lists a file twice', p);
end
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
h = lower(reshape(dec2hex(typecast(md.digest(), 'uint8'), 2)', 1, []));
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


function say(LOG, varargin)
% print and append to the log (opened and closed each time, so the zip always gets all of it)
msg = sprintf(varargin{:});
fprintf('%s\n', msg);
fid = fopen(LOG, 'a');
fprintf(fid, '%s\n', msg);
fclose(fid);
end
