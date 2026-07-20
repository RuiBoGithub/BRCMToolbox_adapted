function files = export_model_configuration(output_dir, idf_path, ep_version, ...
    idd_file, tables_dir, identifiers, boundary_records, Ts_hrs, x0, ...
    table_names, constraint_identifiers)
%EXPORT_MODEL_CONFIGURATION Export portable model metadata and identifiers.

metadata = struct();
metadata.source_idf = strrep(idf_path, filesep, '/');
metadata.energyplus_version = ep_version;
metadata.idd_file = idd_file;
metadata.sampling_time_hours = Ts_hrs;
metadata.initial_state_definition = 'Uniform 20 degC for every thermal state';
metadata.initial_state_length = numel(x0);
metadata.ehf_declarations = {};
metadata.building_model_note = ...
    'BuildingModel generated with no EHF declarations because the IDF does not declare EHF models.';
metadata.boundary_value_semantics = ...
    'Conductance G [W/K]; generateThermalModel.m stores inverse total resistance.';
metadata.table_order = table_names;
metadata.table_directory = strrep(tables_dir, filesep, '/');

axes = struct();
axes.thermal_A = {'x','x'}; axes.thermal_Bq = {'x','q'};
axes.thermal_Xcap = {'x','x'}; axes.thermal_Ad = {'x','x'};
axes.thermal_Bqd = {'x','q'};
axes.A = {'x','x'}; axes.Bu = {'x','u'}; axes.Bv = {'x','v'};
axes.Bxu = {'x','x','u'}; axes.Bvu = {'x','v','u'};
axes.C = {'y','x'}; axes.Du = {'y','u'}; axes.Dv = {'y','v'};
axes.Dxu = {'y','x','u'}; axes.Dvu = {'y','v','u'};
axes.Ad = {'x','x'}; axes.Bdu = {'x','u'}; axes.Bdv = {'x','v'};
axes.Bdxu = {'x','x','u'}; axes.Bdvu = {'x','v','u'};
axes.Fx = {'constraints','x'}; axes.Fu = {'constraints','u'};
axes.Fv = {'constraints','v'}; axes.g = {'constraints','scalar'};
axes.cu = {'u','scalar'};

write_json(fullfile(output_dir, 'metadata.json'), metadata);
write_json(fullfile(output_dir, 'identifiers.json'), identifiers);
write_json(fullfile(output_dir, 'boundary_conditions.json'), boundary_records);
write_json(fullfile(output_dir, 'matrix_axes.json'), axes);
write_json(fullfile(output_dir, 'constraint_identifiers.json'), constraint_identifiers);
save(fullfile(output_dir, 'initial_state.mat'), 'x0', 'Ts_hrs', '-v7');

files = struct('metadata', 'model_config/metadata.json', ...
    'identifiers', 'model_config/identifiers.json', ...
    'boundary_conditions', 'model_config/boundary_conditions.json', ...
    'matrix_axes', 'model_config/matrix_axes.json', ...
    'constraint_identifiers', 'model_config/constraint_identifiers.json', ...
    'initial_state', 'model_config/initial_state.mat', ...
    'tables', 'model_config/tables/*.csv');
end

function write_json(filename, value)
fid = fopen(filename, 'w');
if fid < 0, error('export_model_configuration:Write', 'Cannot write %s.', filename); end
cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
fprintf(fid, '%s\n', jsonencode(value));
end
