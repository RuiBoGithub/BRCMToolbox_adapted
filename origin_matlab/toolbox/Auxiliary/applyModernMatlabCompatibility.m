function [modified_files, modified_declarations] = applyModernMatlabCompatibility(toolbox_directory)
%APPLYMODERNMATLABCOMPATIBILITY Rewrite legacy property type declarations.
% Converts the retired "property@type" form to the equivalent current
% "property type" form. The operation is idempotent and changes declaration
% syntax only; property names, types, defaults, comments, and class scope are
% preserved.

if nargin < 1 || isempty(toolbox_directory)
    helper_directory = fileparts(mfilename('fullpath'));
    toolbox_directory = fileparts(helper_directory);
end

class_directory = fullfile(toolbox_directory, 'Classes');
if exist(class_directory, 'dir') ~= 7
    error('applyModernMatlabCompatibility:ToolboxNotFound', ...
        'Expected BRCM class directory not found: %s', class_directory);
end

class_files = localGetMFiles(class_directory);
modified_files = {};
modified_declarations = 0;
% Match only the declaration prefix. Defaults can continue onto later lines,
% so requiring a semicolon on this line would miss declarations such as
% "boundary_conditions@struct = struct(...".
expression = ['^(\s*)([A-Za-z]\w*)@', ...
    '([A-Za-z]\w*(?:\.[A-Za-z]\w*)*)(.*)$'];
replacement = '$1$2 $3$4';

for i = 1:numel(class_files)
    filename = class_files{i};
    lines = getLines(filename);
    output = lines;
    file_changes = 0;
    for j = 1:numel(lines)
        converted = regexprep(lines{j}, expression, replacement);
        if ~strcmp(converted, lines{j})
            output{j} = converted;
            file_changes = file_changes + 1;
        end
    end
    if file_changes > 0
        fid = fopen(filename, 'w');
        if fid == -1
            error('applyModernMatlabCompatibility:WriteFailed', ...
                'Cannot update class file: %s', filename);
        end
        cleanup_file = onCleanup(@() fclose(fid)); %#ok<NASGU>
        fprintf(fid, '%s\n', output{:});
        clear cleanup_file
        modified_files{end+1} = filename; %#ok<AGROW>
        modified_declarations = modified_declarations + file_changes;
    end
end
end

function files = localGetMFiles(directory)
entries = dir(directory);
files = {};
for i = 1:numel(entries)
    name = entries(i).name;
    if strcmp(name, '.') || strcmp(name, '..')
        continue;
    end
    path = fullfile(directory, name);
    if entries(i).isdir
        files = [files, localGetMFiles(path)]; %#ok<AGROW>
    else
        [~, ~, extension] = fileparts(name);
        if strcmp(extension, '.m')
            files{end+1} = path; %#ok<AGROW>
        end
    end
end
end
