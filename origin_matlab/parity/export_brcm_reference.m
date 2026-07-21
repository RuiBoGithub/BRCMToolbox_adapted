function export_brcm_reference(output_directory)
%EXPORT_BRCM_REFERENCE Export portable DemoBuilding parity fixtures.
% This function exercises the existing BRCM implementation without changing
% or serializing any BRCM class instances. Numeric arrays are written to
% MATLAB v7 MAT files; identifiers, axes, and loaded input data are JSON.

parity_directory = fileparts(mfilename('fullpath'));
origin_directory = fileparts(parity_directory);
toolbox_directory = fullfile(origin_directory, 'toolbox');
repository_directory = fileparts(origin_directory);
if nargin < 1 || isempty(output_directory)
    output_directory = fullfile(repository_directory, 'tests', 'fixtures', 'matlab');
end
if exist('jsonencode', 'builtin') ~= 5 && exist('jsonencode', 'file') ~= 2
    error('export_brcm_reference:jsonencode', ...
        'This exporter requires a MATLAB release providing jsonencode.');
end
if exist(output_directory, 'dir') ~= 7
    mkdir(output_directory);
end

% Modernize legacy declarations before MATLAB attempts to parse any BRCM
% class, then put this exact toolbox at the front of the search path.
addpath(fullfile(toolbox_directory, 'Auxiliary'), '-begin');
applyModernMatlabCompatibility(toolbox_directory);
addpath(genpath(toolbox_directory), '-begin');
rehash path

expected_building = fullfile(toolbox_directory, 'Classes', '@Building', 'Building.m');
building_definitions = which('Building', '-all');
if ischar(building_definitions)
    building_definitions = cellstr(building_definitions);
elseif isstring(building_definitions)
    building_definitions = cellstr(building_definitions);
end
if isempty(building_definitions)
    error('export_brcm_reference:BuildingNotFound', ...
        'Building is not available after adding toolbox: %s', toolbox_directory);
end
if numel(building_definitions) ~= 1 || ...
        ~strcmp(building_definitions{1}, expected_building)
    error('export_brcm_reference:AmbiguousBuilding', ...
        ['Expected only %s, but which Building -all returned:\n%s\n' ...
         'Remove conflicting BRCM/Building definitions from the MATLAB path.'], ...
        expected_building, strjoin(building_definitions, newline));
end

global g_debugLvl
g_debugLvl = -1;

building_name = 'DemoBuilding';
thermal_data_directory = fullfile(toolbox_directory, 'BuildingData', building_name, 'ThermalModel');
ehf_data_directory = fullfile(toolbox_directory, 'BuildingData', building_name, 'EHFM');

B = Building(building_name);
B.loadThermalModelData(thermal_data_directory);

B.declareEHFModel('BuildingHull.m', fullfile(ehf_data_directory, 'buildinghull'), 'BuildingHull');
B.declareEHFModel('AHU.m', fullfile(ehf_data_directory, 'ahu'), 'AHU1');
B.declareEHFModel('InternalGains.m', fullfile(ehf_data_directory, 'internalgains'), 'IG');
B.declareEHFModel('BEHeatfluxes.m', fullfile(ehf_data_directory, 'BEHeatfluxes'), 'TABS');
B.declareEHFModel('Radiators.m', fullfile(ehf_data_directory, 'radiators'), 'Rad');
B.generateBuildingModel();

Ts_hrs = 0.25;
B.building_model.setDiscretizationStep(Ts_hrs);
B.building_model.discretize();

identifiers = identifiers_to_struct(B.building_model.identifiers);
n_x = length(identifiers.x);
n_q = length(identifiers.q);
n_u = length(identifiers.u);
n_v = length(identifiers.v);
n_y = length(identifiers.y);
n_c = length(identifiers.constraints);

thermal_data = thermal_data_to_struct(B.thermal_model_data);
write_json(fullfile(output_directory, 'thermal_model_data.json'), thermal_data);

thermal_A = B.building_model.thermal_submodel.A;
thermal_Bq = B.building_model.thermal_submodel.Bq;
thermal_Xcap = B.building_model.thermal_submodel.Xcap;
[thermal_A_d, thermal_Bq_d] = B.building_model.thermal_submodel.discretize(Ts_hrs);
save(fullfile(output_directory, 'thermal_model.mat'), 'thermal_A', 'thermal_Bq', ...
    'thermal_Xcap', 'thermal_A_d', 'thermal_Bq_d', '-v7');

matrices = empty_matrix_manifest();
matrices = add_matrix(matrices, 'thermal.A', 'thermal_model.mat', 'thermal_A', [n_x n_x], {'x','x'});
matrices = add_matrix(matrices, 'thermal.Bq', 'thermal_model.mat', 'thermal_Bq', [n_x n_q], {'x','q'});
matrices = add_matrix(matrices, 'thermal.Xcap', 'thermal_model.mat', 'thermal_Xcap', [n_x n_x], {'x','x'});
matrices = add_matrix(matrices, 'thermal.A_d', 'thermal_model.mat', 'thermal_A_d', [n_x n_x], {'x','x'});
matrices = add_matrix(matrices, 'thermal.Bq_d', 'thermal_model.mat', 'thermal_Bq_d', [n_x n_q], {'x','q'});

ehf_models = struct('index', {}, 'class_name', {}, 'identifier', {}, ...
    'source_file', {}, 'mat_file', {}, 'identifiers', {});
for i = 1:length(B.building_model.EHF_submodels)
    ehf = B.building_model.EHF_submodels{i};
    ehf_ids = identifiers_to_struct(ehf.identifiers);
    ehf_class = class(ehf);
    ehf_identifier = ehf.EHF_identifier;
    mat_file = sprintf('ehf_%02d_%s.mat', i, safe_filename(ehf_identifier));

    Aq = ehf.Aq;
    Bq_u = ehf.Bq_u;
    Bq_v = ehf.Bq_v;
    Bq_xu = ehf.Bq_xu;
    Bq_vu = ehf.Bq_vu;
    save(fullfile(output_directory, mat_file), 'Aq', 'Bq_u', 'Bq_v', 'Bq_xu', 'Bq_vu', '-v7');

    ehf_models(end+1) = struct( ... %#ok<AGROW>
        'index', i, 'class_name', ehf_class, 'identifier', ehf_identifier, ...
        'source_file', relative_to_root(ehf.source_file, toolbox_directory), ...
        'mat_file', mat_file, 'identifiers', ehf_ids);

    prefix = sprintf('ehf.%s', ehf_identifier);
    local_n_x = length(ehf_ids.x);
    local_n_q = length(ehf_ids.q);
    local_n_u = length(ehf_ids.u);
    local_n_v = length(ehf_ids.v);
    matrices = add_matrix(matrices, [prefix '.Aq'], mat_file, 'Aq', ...
        [local_n_q local_n_x], {[prefix '.q'], [prefix '.x']});
    matrices = add_matrix(matrices, [prefix '.Bq_u'], mat_file, 'Bq_u', ...
        [local_n_q local_n_u], {[prefix '.q'], [prefix '.u']});
    matrices = add_matrix(matrices, [prefix '.Bq_v'], mat_file, 'Bq_v', ...
        [local_n_q local_n_v], {[prefix '.q'], [prefix '.v']});
    matrices = add_matrix(matrices, [prefix '.Bq_xu'], mat_file, 'Bq_xu', ...
        [local_n_q local_n_x local_n_u], {[prefix '.q'], [prefix '.x'], [prefix '.u']});
    matrices = add_matrix(matrices, [prefix '.Bq_vu'], mat_file, 'Bq_vu', ...
        [local_n_q local_n_v local_n_u], {[prefix '.q'], [prefix '.v'], [prefix '.u']});
end

continuous = B.building_model.continuous_time_model;
A = continuous.A; Bu = continuous.Bu; Bv = continuous.Bv;
Bxu = continuous.Bxu; Bvu = continuous.Bvu;
C = continuous.C; Du = continuous.Du; Dv = continuous.Dv;
Dxu = continuous.Dxu; Dvu = continuous.Dvu;
save(fullfile(output_directory, 'building_continuous.mat'), 'A', 'Bu', 'Bv', ...
    'Bxu', 'Bvu', 'C', 'Du', 'Dv', 'Dxu', 'Dvu', '-v7');
matrices = add_full_model_matrices(matrices, 'continuous', 'building_continuous.mat', ...
    n_x, n_u, n_v, n_y);

discrete = B.building_model.discrete_time_model;
A = discrete.A; Bu = discrete.Bu; Bv = discrete.Bv;
Bxu = discrete.Bxu; Bvu = discrete.Bvu;
C = discrete.C; Du = discrete.Du; Dv = discrete.Dv;
Dxu = discrete.Dxu; Dvu = discrete.Dvu;
save(fullfile(output_directory, 'building_discrete.mat'), 'A', 'Bu', 'Bv', ...
    'Bxu', 'Bvu', 'C', 'Du', 'Dv', 'Dxu', 'Dvu', '-v7');
matrices = add_full_model_matrices(matrices, 'discrete', 'building_discrete.mat', ...
    n_x, n_u, n_v, n_y);

[constraintsParameters, constraint_parameter_names, constraint_parameter_values] = ...
    demo_constraint_parameters(n_x, n_v);
[Fx, Fu, Fv, g, constraint_identifiers] = ...
    B.building_model.getConstraintsMatrices(constraintsParameters);
[costParameters, cost_parameter_names, cost_parameter_values] = demo_cost_parameters();
cu = B.building_model.getCostVector(costParameters);
constraint_AHU1_x = constraintsParameters.AHU1.x;
constraint_AHU1_v_fullModel = constraintsParameters.AHU1.v_fullModel;
save(fullfile(output_directory, 'constraints_cost.mat'), 'Fx', 'Fu', 'Fv', 'g', 'cu', ...
    'constraint_AHU1_x', 'constraint_AHU1_v_fullModel', ...
    'constraint_parameter_values', 'cost_parameter_values', '-v7');
matrices = add_matrix(matrices, 'constraints.Fx', 'constraints_cost.mat', 'Fx', [n_c n_x], {'constraints','x'});
matrices = add_matrix(matrices, 'constraints.Fu', 'constraints_cost.mat', 'Fu', [n_c n_u], {'constraints','u'});
matrices = add_matrix(matrices, 'constraints.Fv', 'constraints_cost.mat', 'Fv', [n_c n_v], {'constraints','v'});
matrices = add_matrix(matrices, 'constraints.g', 'constraints_cost.mat', 'g', [n_c 1], {'constraints','scalar'});
matrices = add_matrix(matrices, 'cost.cu', 'constraints_cost.mat', 'cu', [n_u 1], {'u','scalar'});
matrices = add_matrix(matrices, 'parameters.AHU1.x', 'constraints_cost.mat', 'constraint_AHU1_x', [n_x 1], {'x','scalar'});
matrices = add_matrix(matrices, 'parameters.AHU1.v_fullModel', 'constraints_cost.mat', 'constraint_AHU1_v_fullModel', [n_v 1], {'v','scalar'});
matrices = add_matrix(matrices, 'parameters.constraint_values', 'constraints_cost.mat', ...
    'constraint_parameter_values', [length(constraint_parameter_names) 1], {'constraint_parameters','scalar'});
matrices = add_matrix(matrices, 'parameters.cost_values', 'constraints_cost.mat', ...
    'cost_parameter_values', [length(cost_parameter_names) 1], {'cost_parameters','scalar'});

n_time_steps = 24 * 4;
x0 = 22 * ones(n_x, 1);
requested_U = zeros(n_u, n_time_steps);
requested_V = zeros(n_v, n_time_steps);
idx_u_rad_Offices = getIdIndex(identifiers.u, 'u_rad_Offices');
idx_v_Tamb = getIdIndex(identifiers.v, 'v_Tamb');
requested_V(idx_v_Tamb, :) = 22;
requested_U(idx_u_rad_Offices, 5:end) = 5;

SimExp = SimulationExperiment(B);
SimExp.setNumberOfSimulationTimeSteps(n_time_steps);
SimExp.setInitialState(x0);
[X, U, V, t_hrs] = SimExp.simulateBuildingModel('inputTrajectory', requested_U, requested_V);
save(fullfile(output_directory, 'simulation.mat'), 'x0', 'requested_U', 'requested_V', ...
    'X', 'U', 'V', 't_hrs', '-v7');
matrices = add_matrix(matrices, 'simulation.x0', 'simulation.mat', 'x0', [n_x 1], {'x','scalar'});
matrices = add_matrix(matrices, 'simulation.requested_U', 'simulation.mat', 'requested_U', [n_u n_time_steps], {'u','time'});
matrices = add_matrix(matrices, 'simulation.requested_V', 'simulation.mat', 'requested_V', [n_v n_time_steps], {'v','time'});
matrices = add_matrix(matrices, 'simulation.X', 'simulation.mat', 'X', [n_x n_time_steps], {'x','time'});
matrices = add_matrix(matrices, 'simulation.U', 'simulation.mat', 'U', [n_u n_time_steps], {'u','time'});
matrices = add_matrix(matrices, 'simulation.V', 'simulation.mat', 'V', [n_v n_time_steps], {'v','time'});
matrices = add_matrix(matrices, 'simulation.t_hrs', 'simulation.mat', 't_hrs', [1 n_time_steps], {'scalar','time'});

manifest = struct();
manifest.format = 'brcm-matlab-reference';
manifest.format_version = 1;
manifest.building_name = building_name;
manifest.toolbox_version = '1.03';
manifest.matlab_version = version;
manifest.sampling_time_hours = Ts_hrs;
manifest.simulation_time_steps = n_time_steps;
manifest.thermal_data_file = 'thermal_model_data.json';
manifest.identifiers = identifiers;
manifest.constraint_identifiers_returned = reshape_cellstr(constraint_identifiers);
manifest.ehf_models = ehf_models;
manifest.constraint_parameter_names = constraint_parameter_names;
manifest.cost_parameter_names = cost_parameter_names;
manifest.matrices = matrices;
write_json(fullfile(output_directory, 'manifest.json'), manifest);

fprintf('BRCM reference fixtures written to %s\n', output_directory);
end

function ids = identifiers_to_struct(identifier_object)
ids = struct('x', {reshape_cellstr(identifier_object.x)}, ...
    'q', {reshape_cellstr(identifier_object.q)}, ...
    'u', {reshape_cellstr(identifier_object.u)}, ...
    'v', {reshape_cellstr(identifier_object.v)}, ...
    'y', {reshape_cellstr(identifier_object.y)}, ...
    'constraints', {reshape_cellstr(identifier_object.constraints)});
end

function out = reshape_cellstr(in)
if isempty(in)
    out = {};
elseif ischar(in)
    out = {in};
else
    out = reshape(in, 1, []);
end
end

function data = thermal_data_to_struct(tmd)
data = struct();
data.zones = struct('identifier', {}, 'description', {}, 'area', {}, 'volume', {}, 'group', {});
for i = 1:length(tmd.zones)
    o = tmd.zones(i);
    data.zones(end+1) = struct('identifier', o.identifier, 'description', o.description, ...
        'area', o.area, 'volume', o.volume, 'group', {reshape_cellstr(o.group)}); %#ok<AGROW>
end
data.building_elements = struct('identifier', {}, 'description', {}, 'construction_identifier', {}, ...
    'adjacent_A', {}, 'adjacent_B', {}, 'window_identifier', {}, 'area', {}, 'vertices', {});
for i = 1:length(tmd.building_elements)
    o = tmd.building_elements(i);
    data.building_elements(end+1) = struct('identifier', o.identifier, 'description', o.description, ...
        'construction_identifier', o.construction_identifier, 'adjacent_A', o.adjacent_A, ...
        'adjacent_B', o.adjacent_B, 'window_identifier', o.window_identifier, ...
        'area', o.area, 'vertices', vertices_to_plain(o.vertices)); %#ok<AGROW>
end
data.constructions = struct('identifier', {}, 'description', {}, 'material_identifiers', {}, ...
    'thickness', {}, 'conv_coeff_adjacent_A', {}, 'conv_coeff_adjacent_B', {});
for i = 1:length(tmd.constructions)
    o = tmd.constructions(i);
    data.constructions(end+1) = struct('identifier', o.identifier, 'description', o.description, ...
        'material_identifiers', {reshape_cellstr(o.material_identifiers)}, ...
        'thickness', {reshape_cellstr(o.thickness)}, ...
        'conv_coeff_adjacent_A', o.conv_coeff_adjacent_A, ...
        'conv_coeff_adjacent_B', o.conv_coeff_adjacent_B); %#ok<AGROW>
end
data.nomass_constructions = copy_simple_records(tmd.nomass_constructions, ...
    {'identifier','description','U_value'});
data.materials = copy_simple_records(tmd.materials, ...
    {'identifier','description','specific_heat_capacity','specific_thermal_resistance','density','R_value'});
data.windows = copy_simple_records(tmd.windows, ...
    {'identifier','description','glass_area','frame_area','U_value','SHGC'});
data.parameters = copy_simple_records(tmd.parameters, {'identifier','description','value'});
% Encoding cells of scalar structs guarantees a JSON array even for groups
% such as DemoBuilding's single no-mass construction.
groups = fieldnames(data);
for i = 1:length(groups)
    data.(groups{i}) = reshape(num2cell(data.(groups{i})), 1, []);
end
end

function records = copy_simple_records(objects, fields)
template = cell2struct(cell(size(fields)), fields, 2);
records = repmat(template, 0, 1);
for i = 1:length(objects)
    record = template;
    for j = 1:length(fields)
        record.(fields{j}) = objects(i).(fields{j});
    end
    records(end+1) = record; %#ok<AGROW>
end
end

function value = vertices_to_plain(vertices)
if isempty(vertices)
    value = [];
elseif ischar(vertices)
    value = vertices;
else
    value = zeros(length(vertices), 3);
    for i = 1:length(vertices)
        value(i, :) = [vertices(i).x vertices(i).y vertices(i).z];
    end
end
end

function matrices = empty_matrix_manifest()
matrices = struct('key', {}, 'file', {}, 'variable', {}, 'shape', {}, 'axes', {});
end

function matrices = add_matrix(matrices, key, file, variable, shape, axes)
matrices(end+1) = struct('key', key, 'file', file, 'variable', variable, ...
    'shape', shape, 'axes', {axes});
end

function matrices = add_full_model_matrices(matrices, prefix, file, n_x, n_u, n_v, n_y)
matrices = add_matrix(matrices, [prefix '.A'], file, 'A', [n_x n_x], {'x','x'});
matrices = add_matrix(matrices, [prefix '.Bu'], file, 'Bu', [n_x n_u], {'x','u'});
matrices = add_matrix(matrices, [prefix '.Bv'], file, 'Bv', [n_x n_v], {'x','v'});
matrices = add_matrix(matrices, [prefix '.Bxu'], file, 'Bxu', [n_x n_x n_u], {'x','x','u'});
matrices = add_matrix(matrices, [prefix '.Bvu'], file, 'Bvu', [n_x n_v n_u], {'x','v','u'});
matrices = add_matrix(matrices, [prefix '.C'], file, 'C', [n_y n_x], {'y','x'});
matrices = add_matrix(matrices, [prefix '.Du'], file, 'Du', [n_y n_u], {'y','u'});
matrices = add_matrix(matrices, [prefix '.Dv'], file, 'Dv', [n_y n_v], {'y','v'});
matrices = add_matrix(matrices, [prefix '.Dxu'], file, 'Dxu', [n_y n_x n_u], {'y','x','u'});
matrices = add_matrix(matrices, [prefix '.Dvu'], file, 'Dvu', [n_y n_v n_u], {'y','v','u'});
end

function [p, names, values] = demo_constraint_parameters(n_x, n_v)
p = struct();
p.AHU1.mdot_min = 0; p.AHU1.mdot_max = 1;
p.AHU1.T_supply_min = 22; p.AHU1.T_supply_max = 30;
p.AHU1.Q_heat_min = 0; p.AHU1.Q_heat_max = 1000;
p.AHU1.Q_cool_min = 0; p.AHU1.Q_cool_max = 1;
p.AHU1.x = 23 * ones(n_x, 1);
p.AHU1.v_fullModel = 20 * ones(n_v, 1);
p.BuildingHull.BPos_blinds_E_min = 0.1; p.BuildingHull.BPos_blinds_E_max = 1;
p.BuildingHull.BPos_blinds_L_min = 0.1; p.BuildingHull.BPos_blinds_L_max = 1;
p.BuildingHull.BPos_blinds_N_min = 0.1; p.BuildingHull.BPos_blinds_N_max = 1;
p.BuildingHull.BPos_blinds_S_min = 0.1; p.BuildingHull.BPos_blinds_S_max = 1;
p.BuildingHull.BPos_blinds_W_min = 0.1; p.BuildingHull.BPos_blinds_W_max = 1;
p.TABS.Q_BEH_hTABS_heat_min = 100; p.TABS.Q_BEH_hTABS_heat_max = 1000;
p.TABS.Q_BEH_cTABS_cool_min = 100; p.TABS.Q_BEH_cTABS_cool_max = 1000;
p.Rad.Q_rad_CornerOffices_min = 1; p.Rad.Q_rad_CornerOffices_max = 3;
p.Rad.Q_rad_Offices_min = 2; p.Rad.Q_rad_Offices_max = 4;
names = {'AHU1.mdot_min','AHU1.mdot_max','AHU1.T_supply_min','AHU1.T_supply_max', ...
    'AHU1.Q_heat_min','AHU1.Q_heat_max','AHU1.Q_cool_min','AHU1.Q_cool_max', ...
    'BuildingHull.BPos_blinds_E_min','BuildingHull.BPos_blinds_E_max', ...
    'BuildingHull.BPos_blinds_L_min','BuildingHull.BPos_blinds_L_max', ...
    'BuildingHull.BPos_blinds_N_min','BuildingHull.BPos_blinds_N_max', ...
    'BuildingHull.BPos_blinds_S_min','BuildingHull.BPos_blinds_S_max', ...
    'BuildingHull.BPos_blinds_W_min','BuildingHull.BPos_blinds_W_max', ...
    'TABS.Q_BEH_hTABS_heat_min','TABS.Q_BEH_hTABS_heat_max', ...
    'TABS.Q_BEH_cTABS_cool_min','TABS.Q_BEH_cTABS_cool_max', ...
    'Rad.Q_rad_CornerOffices_min','Rad.Q_rad_CornerOffices_max', ...
    'Rad.Q_rad_Offices_min','Rad.Q_rad_Offices_max'};
values = [0;1;22;30;0;1000;0;1;0.1;1;0.1;1;0.1;1;0.1;1;0.1;1;100;1000;100;1000;1;3;2;4];
end

function [p, names, values] = demo_cost_parameters()
p = struct();
p.Rad.costPerJouleHeated = 10;
p.TABS.costPerJouleCooled = 10; p.TABS.costPerJouleHeated = 10;
p.AHU1.costPerKgAirTransported = 1;
p.AHU1.costPerJouleCooled = 10;
p.AHU1.costPerKgCooledByEvapCooler = 10;
p.AHU1.costPerJouleHeated = 10;
names = {'Rad.costPerJouleHeated','TABS.costPerJouleCooled', ...
    'TABS.costPerJouleHeated','AHU1.costPerKgAirTransported', ...
    'AHU1.costPerJouleCooled','AHU1.costPerKgCooledByEvapCooler', ...
    'AHU1.costPerJouleHeated'};
values = [10;10;10;1;10;10;10];
end

function write_json(filename, value)
encoded = jsonencode(value);
fid = fopen(filename, 'w');
if fid < 0
    error('export_brcm_reference:write', 'Cannot open %s for writing.', filename);
end
cleanup_file = onCleanup(@() fclose(fid)); %#ok<NASGU>
fprintf(fid, '%s\n', encoded);
end

function out = safe_filename(in)
out = regexprep(in, '[^A-Za-z0-9_-]', '_');
end

function out = relative_to_root(path_value, root_directory)
prefix = [root_directory filesep];
if strncmp(path_value, prefix, length(prefix))
    out = path_value(length(prefix)+1:end);
else
    out = path_value;
end
out = strrep(out, filesep, '/');
end
