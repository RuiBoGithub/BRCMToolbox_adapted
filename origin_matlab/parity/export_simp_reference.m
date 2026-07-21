function export_simp_reference(output_directory)
%EXPORT_SIMP_REFERENCE Export an operational BRCM reference from _simp.idf.

this_file = mfilename('fullpath');
parity_dir = fileparts(this_file);
origin_matlab_dir = fileparts(parity_dir);
toolbox_directory = fullfile(origin_matlab_dir, 'toolbox');
repository_root = fileparts(origin_matlab_dir);
idf_file = fullfile(repository_root, 'tests', 'fixtures', 'energyplus', '_simp.idf');
if nargin < 1 || isempty(output_directory)
    output_directory = fullfile(repository_root, 'outputs', 'parity', 'simp', 'matlab');
end
assert(isfolder(toolbox_directory), 'export_simp_reference:ToolboxNotFound', ...
    'Resolved MATLAB toolbox directory does not exist: %s', toolbox_directory);
assert(isfile(idf_file), 'export_simp_reference:IDFNotFound', ...
    'Required source IDF does not exist: %s', idf_file);

addpath(fullfile(toolbox_directory, 'Auxiliary'), '-begin');
applyModernMatlabCompatibility(toolbox_directory);
addpath(genpath(toolbox_directory), '-begin');
rehash toolboxcache
expected_building = fullfile(toolbox_directory, 'Classes', '@Building', 'Building.m');
building_definitions = which('Building', '-all');
if ischar(building_definitions)
    building_definitions = cellstr(building_definitions);
elseif isstring(building_definitions)
    building_definitions = cellstr(building_definitions);
end
if numel(building_definitions) ~= 1 || ~strcmp(building_definitions{1}, expected_building)
    error('export_simp_reference:AmbiguousBuilding', ...
        'Expected only %s from which Building -all.', expected_building);
end

if ~isfolder(output_directory)
    mkdir(output_directory);
end
conversion_directory = fullfile(output_directory, 'conversion_tables');
table_directory = fullfile(output_directory, 'tables');
reset_directory(conversion_directory);
reset_directory(table_directory);

global g_debugLvl
g_debugLvl = -1;
idf_sha256 = sha256_file(idf_file);

old_directory = pwd;
cleanup_directory = onCleanup(@() cd(old_directory)); %#ok<NASGU>
convertIDFToBRCM(idf_file, conversion_directory, true);

B = Building('simp');
B.loadThermalModelData(conversion_directory);
% Re-export all seven loaded conversion tables as deterministic CSV files.
% The parity helper emits schema-only tables for valid empty optional data.
tables = safeConvertThermalModelDataToCells(B.thermal_model_data);
table_names = {'zones', 'buildingelements', 'constructions', 'materials', ...
    'windows', 'parameters', 'nomassconstructions'};
for i = 1:length(table_names)
    name = table_names{i};
    writeCellToFile(tables.(name), fullfile(table_directory, name), true);
end
B.generateThermalModel();

A = B.building_model.thermal_submodel.A;
Bq = B.building_model.thermal_submodel.Bq;
Xcap = B.building_model.thermal_submodel.Xcap;
state_identifiers = reshape_cellstr(B.building_model.identifiers.x);
heat_flux_identifiers = reshape_cellstr(B.building_model.identifiers.q);
boundaries = boundaries_to_plain(B.building_model.boundary_conditions);

Ts = 0.25;
N = 16;
n_x = length(state_identifiers);
n_q = length(heat_flux_identifiers);
x0 = 20 + 0.01 * (1:n_x)';
Q = zeros(n_q, N);
for k = 1:N
    Q(:, k) = 100 + 0.5 * (1:n_q)' + 2 * (k - 1);
end
B.building_model.setDiscretizationStep(Ts);
experiment = SimulationExperiment(B);
experiment.setNumberOfSimulationTimeSteps(N);
experiment.setInitialState(x0);
[X, Q_returned, t_hrs] = experiment.simulateThermalModel('inputTrajectory', Q);
assert(isequal(Q, Q_returned), 'export_simp_reference:SimulationInput', ...
    'MATLAB simulation did not return the requested deterministic Q trajectory.');

save(fullfile(output_directory, 'reference.mat'), 'A', 'Bq', 'Xcap', ...
    'X', 'Q', 't_hrs', 'x0', 'Ts', 'N', '-v7');
write_json(fullfile(output_directory, 'identifiers.json'), struct( ...
    'state', {state_identifiers}, 'heat_flux', {heat_flux_identifiers}));
write_json(fullfile(output_directory, 'boundaries.json'), boundaries);
manifest = struct('format', 'brcm-simp-matlab-reference', 'format_version', 1, ...
    'source_idf', '_simp.idf', 'source_idf_path', idf_file, ...
    'source_idf_sha256', idf_sha256, 'tables_directory', 'tables', ...
    'matrix_file', 'reference.mat', 'sampling_time_hours', Ts, ...
    'number_of_steps', N, 'matlab_executed', true);
write_json(fullfile(output_directory, 'manifest.json'), manifest);
fprintf('Exported _simp.idf MATLAB reference to %s\n', output_directory);
end

function reset_directory(directory)
if isfolder(directory)
    rmdir(directory, 's');
end
mkdir(directory);
end

function value = sha256_file(filename)
fid = fopen(filename, 'rb');
if fid < 0
    error('export_simp_reference:HashRead', 'Cannot read source IDF: %s', filename);
end
cleanup_file = onCleanup(@() fclose(fid)); %#ok<NASGU>
bytes = fread(fid, Inf, '*uint8');
digest = java.security.MessageDigest.getInstance('SHA-256');
digest.update(bytes);
value = lower(reshape(dec2hex(typecast(digest.digest(), 'uint8'), 2).', 1, []));
end

function out = boundaries_to_plain(boundaries)
out = struct();
names = fieldnames(boundaries);
for i = 1:length(names)
    name = names{i};
    source = boundaries.(name);
    records = cell(1, length(source));
    for j = 1:length(source)
        records{j} = struct('identifier_1', source(j).identifier_1, ...
            'identifier_2', source(j).identifier_2, 'value', source(j).value);
    end
    out.(name) = records;
end
end

function out = reshape_cellstr(in)
out = reshape(in, 1, []);
end

function write_json(filename, value)
fid = fopen(filename, 'w');
if fid < 0
    error('export_simp_reference:Write', 'Cannot write %s', filename);
end
cleanup_file = onCleanup(@() fclose(fid)); %#ok<NASGU>
fprintf(fid, '%s\n', jsonencode(value));
end
