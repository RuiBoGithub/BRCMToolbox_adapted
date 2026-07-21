function tables = safeConvertThermalModelDataToCells(thermal_model_data)
%SAFECONVERTTHERMALMODELDATATOCELLS Convert all seven logical BRCM tables.
% Required datasets use the original converters. Optional empty datasets
% are represented by their exact schema header and no fabricated rows.

tables = struct();
tables.zones = thermal_model_data.convertZone2Cell();
tables.buildingelements = thermal_model_data.convertBuildingElement2Cell();
tables.constructions = thermal_model_data.convertConstruction2Cell();
tables.materials = thermal_model_data.convertMaterial2Cell();

if isempty(thermal_model_data.windows)
    tables.windows = Constants.window_file_header;
else
    tables.windows = thermal_model_data.convertWindow2Cell();
end

if isempty(thermal_model_data.parameters)
    tables.parameters = Constants.parameter_file_header;
else
    tables.parameters = thermal_model_data.convertParameter2Cell();
end

if isempty(thermal_model_data.nomass_constructions)
    tables.nomassconstructions = Constants.nomass_construction_file_header;
else
    tables.nomassconstructions = thermal_model_data.convertNoMassConstruction2Cell();
end
end
