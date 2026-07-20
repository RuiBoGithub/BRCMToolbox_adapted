function manifest = run_brcm_end_to_end(idf_path, output_dir)
%RUN_BRCM_END_TO_END Native MATLAB EnergyPlus -> BRCM -> RC validation.
% Additive validation code only; original BRCM source files are unchanged.

validation_dir = fileparts(mfilename('fullpath'));
root_dir = fileparts(validation_dir);
if nargin < 1 || isempty(idf_path)
    idf_path = fullfile(root_dir, 'tests', 'fixtures', 'energyplus', ...
        'representative_multizone.idf');
end
if nargin < 2 || isempty(output_dir)
    output_dir = fullfile(validation_dir, 'outputs');
end
idf_path = absolute_path(idf_path, root_dir);
output_dir = absolute_path(output_dir, root_dir);

model_config_dir = fullfile(output_dir, 'model_config');
generated_data_dir = fullfile(model_config_dir, 'generated_brcm');
tables_dir = fullfile(model_config_dir, 'tables');
matrices_dir = fullfile(output_dir, 'matrices');
simulation_dir = fullfile(output_dir, 'simulation');
ensure_dir(output_dir); ensure_dir(model_config_dir); ensure_dir(generated_data_dir);
ensure_dir(tables_dir); ensure_dir(matrices_dir); ensure_dir(simulation_dir);

addpath(genpath(root_dir));
old_dir = pwd;
cleanup_dir = onCleanup(@() cd(old_dir)); %#ok<NASGU>
cd(root_dir);
global g_debugLvl
g_debugLvl = 1;

manifest = struct();
manifest.schema_version = 1;
manifest.source_idf = relative_path(idf_path, root_dir);
manifest.source_files = {relative_path(idf_path, root_dir), ...
    'EP2BRCM/convertIDFToBRCM.m', 'Classes/@Building/generateThermalModel.m', ...
    'Classes/@Building/generateBuildingModel.m', ...
    'Classes/@BuildingModel/discretize.m', ...
    'notebooks/BRCM_EnergyPlus_End_to_End.ipynb'};
manifest.output_directory = relative_path(output_dir, root_dir);
manifest.matlab_version = version;
manifest.brcm_root = strrep(root_dir, filesep, '/');
manifest.stages = struct('conversion', 'NOT_RUN', 'tables', 'NOT_RUN', ...
    'thermal_model', 'NOT_RUN', 'building_model', 'NOT_RUN', ...
    'discretization', 'NOT_RUN', 'simulation', 'NOT_RUN', ...
    'repeatability', 'NOT_RUN');
manifest.warnings = {};
manifest.errors = {};
manifest.overall_status = 'FAIL';

try
    if exist(idf_path, 'file') ~= 2
        error('run_brcm_end_to_end:IDF', 'IDF not found: %s', idf_path);
    end
    [energyplus_version, idd_file] = idf_version_and_idd(idf_path);
    manifest.energyplus_version = energyplus_version;
    manifest.idd_file = idd_file;

    lastwarn('');
    convertIDFToBRCM(idf_path, generated_data_dir, true);
    manifest.stages.conversion = 'PASS';
    manifest.warnings = append_last_warning(manifest.warnings);

    B = Building('RepresentativeMultiZone');
    B.loadThermalModelData(generated_data_dir);
    B.writeThermalModelData(tables_dir, true, true);
    table_names = {'zones','buildingelements','constructions','materials', ...
        'windows','parameters','nomassconstructions'};
    table_files = cell(size(table_names));
    for i = 1:numel(table_names)
        table_files{i} = fullfile(tables_dir, [table_names{i} '.csv']);
        if exist(table_files{i}, 'file') ~= 2
            error('run_brcm_end_to_end:Table', 'Missing table: %s', table_files{i});
        end
    end
    manifest.stages.tables = 'PASS';

    % No EHF declarations are implicit in an IDF. Generate an empty-EHF
    % BuildingModel, matching the optional composition in the Python notebook.
    B.generateBuildingModel();
    manifest.stages.thermal_model = 'PASS';
    manifest.stages.building_model = 'PASS';

    Ts_hrs = 1/60;
    B.building_model.setDiscretizationStep(Ts_hrs);
    B.building_model.discretize();
    manifest.stages.discretization = 'PASS';

    ids = identifiers_to_struct(B.building_model.identifiers);
    n_x = numel(ids.x); n_q = numel(ids.q); n_u = numel(ids.u);
    n_v = numel(ids.v); n_y = numel(ids.y); n_c = numel(ids.constraints);
    manifest.model_dimensions = struct('n_x', n_x, 'n_q', n_q, 'n_u', n_u, ...
        'n_v', n_v, 'n_y', n_y, 'n_constraints', n_c);

    tm = B.building_model.thermal_submodel;
    thermal_A = tm.A; thermal_Bq = tm.Bq; thermal_Xcap = tm.Xcap;
    [thermal_Ad, thermal_Bqd] = tm.discretize(Ts_hrs);
    thermal_A_d = thermal_Ad; thermal_Bq_d = thermal_Bqd; % Stage 1 aliases.
    if ~all_finite(thermal_A) || ~all_finite(thermal_Bq) || ...
            ~all_finite(thermal_Xcap) || ~all_finite(thermal_Ad) || ...
            ~all_finite(thermal_Bqd)
        error('run_brcm_end_to_end:Finite', 'Thermal matrices contain NaN or Inf.');
    end
    if any(diag(thermal_Xcap) <= 0)
        error('run_brcm_end_to_end:Capacity', 'Thermal capacitances are not positive.');
    end
    save(fullfile(matrices_dir, 'thermal_model.mat'), 'thermal_A', 'thermal_Bq', ...
        'thermal_Xcap', 'thermal_Ad', 'thermal_Bqd', 'thermal_A_d', ...
        'thermal_Bq_d', '-v7');

    continuous = B.building_model.continuous_time_model;
    A = continuous.A; Bu = continuous.Bu; Bv = continuous.Bv;
    Bxu = continuous.Bxu; Bvu = continuous.Bvu; C = continuous.C;
    Du = continuous.Du; Dv = continuous.Dv; Dxu = continuous.Dxu; Dvu = continuous.Dvu;
    if ~all_finite_fields({A,Bu,Bv,Bxu,Bvu,C,Du,Dv,Dxu,Dvu})
        error('run_brcm_end_to_end:Finite', 'Continuous BuildingModel contains NaN or Inf.');
    end
    save(fullfile(matrices_dir, 'building_continuous.mat'), 'A','Bu','Bv','Bxu', ...
        'Bvu','C','Du','Dv','Dxu','Dvu','-v7');

    discrete = B.building_model.discrete_time_model;
    Ad = discrete.A; Bdu = discrete.Bu; Bdv = discrete.Bv;
    Bdxu = discrete.Bxu; Bdvu = discrete.Bvu; Cd = discrete.C;
    Ddu = discrete.Du; Ddv = discrete.Dv; Ddxu = discrete.Dxu; Ddvu = discrete.Dvu;
    if ~all_finite_fields({Ad,Bdu,Bdv,Bdxu,Bdvu,Cd,Ddu,Ddv,Ddxu,Ddvu})
        error('run_brcm_end_to_end:Finite', 'Discrete BuildingModel contains NaN or Inf.');
    end
    save(fullfile(matrices_dir, 'building_discrete.mat'), 'Ad','Bdu','Bdv', ...
        'Bdxu','Bdvu','Cd','Ddu','Ddv','Ddxu','Ddvu','-v7');

    [Fx, Fu, Fv, g, constraint_identifiers] = ...
        B.building_model.getConstraintsMatrices(struct());
    cu = B.building_model.getCostVector(struct());
    save(fullfile(matrices_dir, 'constraints_cost.mat'), 'Fx','Fu','Fv','g','cu','-v7');

    boundary_records = boundary_conditions_to_struct(B.building_model.boundary_conditions);
    initial_temperature_C = 20;
    ambient_temperature_C = 30;
    zone_heating_W = 0;
    n_steps = 60;
    x0 = initial_temperature_C * ones(n_x, 1);
    [X, X_full, Q, t_hrs] = thermal_simulation(thermal_Ad, thermal_Bqd, ...
        ids, boundary_records, x0, Ts_hrs, n_steps, ambient_temperature_C, zone_heating_W);
    [X_repeat, X_full_repeat, Q_repeat, t_repeat] = thermal_simulation( ...
        thermal_Ad, thermal_Bqd, ids, boundary_records, x0, Ts_hrs, ...
        n_steps, ambient_temperature_C, zone_heating_W);
    if ~all_finite(X_full) || ~all_finite(Q)
        error('run_brcm_end_to_end:SimulationFinite', 'Simulation contains NaN or Inf.');
    end
    manifest.stages.simulation = 'PASS';
    deterministic_repeat = isequaln(X, X_repeat) && isequaln(X_full, X_full_repeat) ...
        && isequaln(Q, Q_repeat) && isequaln(t_hrs, t_repeat);
    if ~deterministic_repeat
        error('run_brcm_end_to_end:Repeatability', 'Repeated simulation differs.');
    end
    manifest.stages.repeatability = 'PASS';

    U = zeros(n_u, n_steps); V = zeros(n_v, n_steps); Y = zeros(n_y, n_steps);
    simulation_config = struct('INITIAL_TEMPERATURE_C', initial_temperature_C, ...
        'AMBIENT_TEMPERATURE_C', ambient_temperature_C, ...
        'ZONE_HEATING_W', zone_heating_W, 'SAMPLE_TIME_HOURS', Ts_hrs, ...
        'N_STEPS', n_steps, 'input_rule', ...
        'For each ambient boundary: q = G * (Tamb - T_boundary_state)', ...
        'boundary_value_semantics', ...
        'Conductance G [W/K], verified from generateThermalModel.m inverse-resistance assignment');
    simulation_summary = export_simulation_results(simulation_dir, x0, Ts_hrs, ...
        n_steps, Q, U, V, X, X_full, Y, t_hrs, ids, simulation_config, deterministic_repeat);

    config_files = export_model_configuration(model_config_dir, idf_path, ...
        energyplus_version, idd_file, tables_dir, ids, boundary_records, ...
        Ts_hrs, x0, table_names, constraint_identifiers);

    manifest.files = struct();
    manifest.files.model_configuration = config_files;
    manifest.files.thermal_matrices = 'matrices/thermal_model.mat';
    manifest.files.continuous_building_model = 'matrices/building_continuous.mat';
    manifest.files.discrete_building_model = 'matrices/building_discrete.mat';
    manifest.files.constraints_cost = 'matrices/constraints_cost.mat';
    manifest.files.simulation_configuration = 'simulation/simulation_config.json';
    manifest.files.simulation_results = 'simulation/simulation_results.mat';
    manifest.files.simulation_summary = 'simulation/simulation_summary.json';
    manifest.matrix_shapes = matrix_shapes(thermal_A, thermal_Bq, thermal_Xcap, ...
        thermal_Ad, thermal_Bqd, A, Bu, Bv, Bxu, Bvu, Ad, Bdu, Bdv, Bdxu, Bdvu);
    manifest.simulation_settings = simulation_config;
    manifest.simulation_summary = simulation_summary;
    manifest.overall_status = 'PASS';
catch err
    manifest.errors{end+1} = struct('identifier', err.identifier, ...
        'message', err.message, 'report', getReport(err, 'extended', 'hyperlinks', 'off'));
    write_json(fullfile(output_dir, 'manifest.json'), manifest);
    rethrow(err);
end

write_json(fullfile(output_dir, 'manifest.json'), manifest);
fprintf('BRCM MATLAB end-to-end validation: %s\n', manifest.overall_status);
fprintf('Manifest: %s\n', fullfile(output_dir, 'manifest.json'));
end

function [X, X_full, Q, t_hrs] = thermal_simulation(Ad, Bqd, ids, boundaries, ...
    x0, Ts_hrs, n_steps, ambient_temperature_C, zone_heating_W)
n_x = numel(ids.x); n_q = numel(ids.q);
X_full = zeros(n_x, n_steps + 1); X_full(:,1) = x0;
Q = zeros(n_q, n_steps); t_hrs = (0:n_steps-1) * Ts_hrs;
for k = 1:n_steps
    q = zeros(n_q, 1);
    for j = 1:numel(boundaries)
        bc = boundaries(j);
        if ~strcmp(bc.type, 'ambient'), continue; end
        if any(strcmp(ids.x, bc.identifier_1))
            state_id = bc.identifier_1;
        elseif any(strcmp(ids.x, bc.identifier_2))
            state_id = bc.identifier_2;
        else
            error('run_brcm_end_to_end:Boundary', ...
                'Ambient boundary has no state endpoint: %s / %s', ...
                bc.identifier_1, bc.identifier_2);
        end
        x_idx = find(strcmp(ids.x, state_id), 1);
        q_id = ['q' state_id(2:end)];
        q_idx = find(strcmp(ids.q, q_id), 1);
        q(q_idx) = q(q_idx) + bc.value * ...
            (ambient_temperature_C - X_full(x_idx,k));
    end
    zone_idx = find(strncmp(ids.x, 'x_Z', 3), 1);
    if ~isempty(zone_idx) && zone_heating_W ~= 0
        q_idx = find(strcmp(ids.q, ['q' ids.x{zone_idx}(2:end)]), 1);
        q(q_idx) = q(q_idx) + zone_heating_W;
    end
    Q(:,k) = q;
    X_full(:,k+1) = Ad * X_full(:,k) + Bqd * q;
end
X = X_full(:,1:n_steps); % MATLAB SimulationExperiment convention.
end

function records = boundary_conditions_to_struct(boundaries)
records = struct('type', {}, 'identifier_1', {}, 'identifier_2', {}, 'value', {});
names = fieldnames(boundaries);
for i = 1:numel(names)
    values = boundaries.(names{i});
    for j = 1:numel(values)
        records(end+1) = struct('type', names{i}, ... %#ok<AGROW>
            'identifier_1', values(j).identifier_1, ...
            'identifier_2', values(j).identifier_2, 'value', values(j).value);
    end
end
end

function out = identifiers_to_struct(value)
out = struct('x', {reshape(value.x,[],1)}, 'q', {reshape(value.q,[],1)}, ...
    'u', {reshape(value.u,[],1)}, 'v', {reshape(value.v,[],1)}, ...
    'y', {reshape(value.y,[],1)}, ...
    'constraints', {reshape(value.constraints,[],1)});
end

function shapes = matrix_shapes(varargin)
names = {'thermal_A','thermal_Bq','thermal_Xcap','thermal_Ad','thermal_Bqd', ...
    'A','Bu','Bv','Bxu','Bvu','Ad','Bdu','Bdv','Bdxu','Bdvu'};
shapes = struct();
for i = 1:numel(names), shapes.(names{i}) = size(varargin{i}); end
end

function result = all_finite(value)
result = isempty(value) || all(isfinite(value(:)));
end

function result = all_finite_fields(values)
result = true;
for i = 1:numel(values), result = result && all_finite(values{i}); end
end

function warnings_out = append_last_warning(warnings_in)
[message, identifier] = lastwarn;
warnings_out = warnings_in;
if ~isempty(message)
    warnings_out{end+1} = struct('identifier', identifier, 'message', message);
    lastwarn('');
end
end

function [version_value, idd_file] = idf_version_and_idd(filename)
text = fileread(filename);
match = regexp(text, '(?i)Version\s*,\s*([^;]+);', 'tokens', 'once');
if isempty(match), error('run_brcm_end_to_end:Version', 'No Version object.'); end
version_value = strtrim(match{1});
if strncmp(version_value,'7.0',3), idd_file = 'V7-0-0-Energy+.idd';
elseif strncmp(version_value,'7.1',3), idd_file = 'V7-1-0-Energy+.idd';
elseif strncmp(version_value,'7.2',3), idd_file = 'V7-2-0-Energy+.idd';
elseif strncmp(version_value,'8.0',3), idd_file = 'V8-0-0-Energy+.idd';
elseif strncmp(version_value,'8.1',3), idd_file = 'V8-1-0-Energy+.idd';
elseif strncmp(version_value,'8.',2), idd_file = 'V8-1-0-Energy+.idd';
else, error('run_brcm_end_to_end:Version', 'Unsupported IDF version %s.', version_value);
end
end

function ensure_dir(path_value)
if exist(path_value, 'dir') ~= 7, mkdir(path_value); end
end

function out = absolute_path(path_value, root_dir)
if isempty(regexp(path_value, '^(/|[A-Za-z]:[\\/])', 'once'))
    out = fullfile(root_dir, path_value);
else
    out = path_value;
end
end

function out = relative_path(path_value, root_dir)
prefix = [root_dir filesep];
if strncmp(path_value, prefix, numel(prefix)), out = path_value(numel(prefix)+1:end);
else, out = path_value; end
out = strrep(out, filesep, '/');
end

function write_json(filename, value)
fid = fopen(filename, 'w');
if fid < 0, error('run_brcm_end_to_end:Write', 'Cannot write %s.', filename); end
cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
fprintf(fid, '%s\n', jsonencode(value));
end
