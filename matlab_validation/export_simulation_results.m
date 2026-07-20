function summary = export_simulation_results(output_dir, x0, Ts_hrs, n_steps, ...
    Q, U, V, X, X_full, Y, t_hrs, identifiers, config, deterministic_repeat)
%EXPORT_SIMULATION_RESULTS Export inputs, results, and compact statistics.

save(fullfile(output_dir, 'simulation_inputs.mat'), 'x0','Ts_hrs','n_steps', ...
    'Q','U','V','-v7');

zone_mask = strncmp(identifiers.x, 'x_Z', 3);
representative_state_identifiers = identifiers.x(zone_mask);
representative_state_trajectories = X_full(zone_mask,:);
state_min = min(X_full, [], 2);
state_max = max(X_full, [], 2);
state_final = X_full(:,end);
save(fullfile(output_dir, 'simulation_results.mat'), 'X','X_full','Y','Q','U','V', ...
    't_hrs','representative_state_identifiers','representative_state_trajectories', ...
    'state_min','state_max','state_final','-v7');

summary = struct('matlab_compatible_X_shape', size(X), ...
    'full_state_shape', size(X_full), 'Q_shape', size(Q), ...
    'U_shape', size(U), 'V_shape', size(V), 'Y_shape', size(Y), ...
    'minimum_state', min(X_full(:)), 'maximum_state', max(X_full(:)), ...
    'final_state', state_final, 'deterministic_repeat', deterministic_repeat);
write_json(fullfile(output_dir, 'simulation_config.json'), config);
write_json(fullfile(output_dir, 'simulation_summary.json'), summary);
end

function write_json(filename, value)
fid = fopen(filename, 'w');
if fid < 0, error('export_simulation_results:Write', 'Cannot write %s.', filename); end
cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
fprintf(fid, '%s\n', jsonencode(value));
end
