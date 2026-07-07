
// A per-model page can render several action forms (e.g. encode / log_prob /
// predict). Each `form.api-form` is wired INDEPENDENTLY: every element it needs
// (params/items containers, add-item button, response area) is resolved RELATIVE
// to that form, and every generated element id is namespaced per-form, so no two
// forms ever share an id or clobber each other's fields.
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.api-form').forEach((form, formIndex) => {
        try {
            initForm(form, formIndex);
        } catch (e) {
            console.error('Failed to initialise form', formIndex, e);
        }
    });
});

function initForm(form, formIndex) {
    // Unique prefix for this form's element ids (label `for=` targets, checkbox ids…).
    const idPrefix = `f${formIndex}-`;

    let schema;
    try {
        schema = JSON.parse(form.dataset.schema || '{}');
    } catch (e) {
        console.error('Failed to parse schema:', e);
        schema = {};
    }

    // Everything below is scoped to THIS form's card.
    const paramsContainer = form.querySelector('.params-container');
    const itemsContainer = form.querySelector('.items-container');
    const addItemBtn = form.querySelector('.add-item-btn');
    const itemsSection = form.querySelector('.items-section');
    const card = form.closest('.endpoint-card') || form.parentNode;
    const responseArea = card ? card.querySelector('.response-area') : null;
    const responseCode = responseArea ? responseArea.querySelector('code') : null;

    if (!paramsContainer || !itemsSection) {
        console.error('Form is missing its params/items containers; skipping.');
        return;
    }

    let itemCounter = 0;

    function createField(name, details, container, itemIndex = null) {
        const fieldId = idPrefix + (itemIndex !== null ? `items-${itemIndex}-${name}` : name);
        const fieldName = itemIndex !== null ? `items[${itemIndex}][${name}]` : `params[${name}]`;

        const group = document.createElement('div');
        group.className = 'form-group';

        let input;
        if (details.is_nested_model && details.nested_fields) {
            // For nested models, don't create a separate label since fieldset has legend
            input = createNestedModelField(name, details);
        } else if (details.enum && details.is_multi_select) {
            // Create label for non-nested fields
            const label = document.createElement('label');
            label.setAttribute('for', fieldId);
            label.textContent = name;
            group.appendChild(label);
            input = createMultiSelectEnum(name, details);
        } else {
            // Create label for all other field types
            const label = document.createElement('label');
            label.setAttribute('for', fieldId);
            label.textContent = name;
            group.appendChild(label);

            if (details.is_list) {
                // A list of scalars (e.g. list[int]); entered as a JSON array so
                // it round-trips correctly (the number branch below would coerce
                // it to a single scalar).
                input = document.createElement('input');
                input.type = 'text';
                input.placeholder = 'JSON array, e.g. [1, 2]';
            } else if (details.enum) {
                input = document.createElement('select');
                details.enum.forEach(val => {
                const option = document.createElement('option');
                option.value = val;
                option.textContent = val;
                    if (details.default === val) option.selected = true;
                    input.appendChild(option);
                });
            } else if (details.type.includes('int') || details.type.includes('float')) {
                input = document.createElement('input');
                input.type = 'number';
                if (details.ge !== null) input.min = details.ge;
                if (details.le !== null) input.max = details.le;
                input.placeholder = `(number, min: ${details.ge ?? 'N/A'}, max: ${details.le ?? 'N/A'})`;
            } else if (details.type.includes('bool')) {
                input = document.createElement('select');
                ['true', 'false'].forEach(val => {
                    const option = document.createElement('option');
                    option.value = val;
                    option.textContent = val;
                    if (String(details.default) === val) option.selected = true;
                    input.appendChild(option);
                });
            } else {
                // Check if this is a biological sequence field
                if ((name.toLowerCase().includes('sequence') || name.toLowerCase().includes('pdb') || name.toLowerCase().includes('smiles')) &&
                    (details.max_length === null || details.max_length > 50)) {
                    input = createBioSequenceInput(name, details);
                } else {
                    input = document.createElement('textarea');
                    input.rows = 3;
                    if (details.min_length !== null) input.minLength = details.min_length;
                    if (details.max_length !== null) input.maxLength = details.max_length;
                    input.placeholder = `(text, min length: ${details.min_length ?? 'N/A'}, max length: ${details.max_length ?? 'N/A'})`;
                }
            }
        }

        input.id = fieldId;
        input.name = fieldName;
        if (details.default !== null && details.default !== undefined) {
            // Array defaults must be JSON-encoded so they parse back to a list.
            input.value = Array.isArray(details.default)
                ? JSON.stringify(details.default)
                : details.default;
        }
        if (details.required) {
            input.required = true;
        }

        // Handle special inputs that have wrapper elements
        if (input._wrapper) {
            group.appendChild(input._wrapper);
        } else {
            group.appendChild(input);
        }

        if (details.description) {
            const small = document.createElement('small');
            small.textContent = details.description;
            group.appendChild(small);
        }

        // Add validation hints if available
        if (details.validation_hints && details.validation_hints.length > 0) {
            const hintsDiv = document.createElement('div');
            hintsDiv.className = 'validation-hints';

            details.validation_hints.forEach(hint => {
                const hintSpan = document.createElement('span');
                hintSpan.className = 'validation-hint';
                hintSpan.textContent = `💡 ${hint}`;
                hintsDiv.appendChild(hintSpan);
            });

            group.appendChild(hintsDiv);
        }

        container.appendChild(group);
    }

    function createBioSequenceInput(name, details) {
        const wrapper = document.createElement('div');
        wrapper.className = 'bio-sequence-wrapper';

        const textarea = document.createElement('textarea');
        textarea.rows = 6;
        textarea.className = 'bio-sequence-input';

        // Determine sequence type for better placeholder
        const sequenceType = getSequenceType(name);
        textarea.placeholder = `Paste ${sequenceType} here...`;

        if (details.min_length !== null) textarea.minLength = details.min_length;
        if (details.max_length !== null) textarea.maxLength = details.max_length;

        // Add character counter
        const counter = document.createElement('div');
        counter.className = 'sequence-counter';
        updateCounter();

        function updateCounter() {
            const len = textarea.value.length;
            const maxLen = details.max_length;
            counter.textContent = maxLen ? `${len}/${maxLen} characters` : `${len} characters`;
            counter.className = `sequence-counter ${len > (maxLen || Infinity) ? 'over-limit' : 'under-limit'}`;
        }

        textarea.addEventListener('input', updateCounter);

        // Add sequence validation hints
        const hints = document.createElement('div');
        hints.className = 'sequence-hints';
        hints.textContent = getSequenceHints(sequenceType);

        wrapper.appendChild(textarea);
        wrapper.appendChild(counter);
        wrapper.appendChild(hints);

        // Set up drag-and-drop AFTER the textarea is added to the wrapper
        textarea._wrapper = wrapper;
        setupDragAndDrop(textarea, name, sequenceType);

        // Return the textarea with wrapper attached
        return textarea;
    }

    function getSequenceType(fieldName) {
        const name = fieldName.toLowerCase();
        if (name.includes('pdb')) return 'PDB structure';
        if (name.includes('smiles')) return 'SMILES string';
        if (name.includes('dna')) return 'DNA sequence';
        if (name.includes('rna')) return 'RNA sequence';
        if (name.includes('protein') || name.includes('sequence')) return 'protein sequence';
        return 'sequence';
    }

    function getSequenceHints(sequenceType) {
        const hints = {
            'protein sequence': 'Use standard amino acid letters (A, C, D, E, F, G, H, I, K, L, M, N, P, Q, R, S, T, V, W, Y)',
            'DNA sequence': 'Use nucleotide letters (A, T, G, C)',
            'RNA sequence': 'Use nucleotide letters (A, U, G, C)',
            'PDB structure': 'Paste PDB file content or upload .pdb file',
            'SMILES string': 'Enter chemical structure in SMILES format'
        };
        return hints[sequenceType] || 'Enter biological sequence data';
    }

    function createMultiSelectEnum(name, details) {
        const container = document.createElement('div');
        container.className = 'multi-select-container';

        // Create hidden input to store the actual values as JSON array
        const hiddenInput = document.createElement('input');
        hiddenInput.type = 'hidden';
        hiddenInput.name = name;

        const selectedValues = new Set();

        // Initialize with default values if present
        if (Array.isArray(details.default)) {
            details.default.forEach(val => selectedValues.add(val));
        }

        function updateHiddenInput() {
            hiddenInput.value = JSON.stringify(Array.from(selectedValues));
        }

        // Create checkboxes for each enum option
        details.enum.forEach(option => {
            const wrapper = document.createElement('div');
            wrapper.className = 'checkbox-wrapper';

            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.value = option;
            checkbox.id = `${idPrefix}${name}-${option}`;
            checkbox.checked = selectedValues.has(option);

            const label = document.createElement('label');
            label.setAttribute('for', checkbox.id);
            label.className = 'checkbox-label';
            label.textContent = option;

            checkbox.addEventListener('change', () => {
                if (checkbox.checked) {
                    selectedValues.add(option);
                } else {
                    selectedValues.delete(option);
                }
                updateHiddenInput();
            });

            wrapper.appendChild(checkbox);
            wrapper.appendChild(label);
            container.appendChild(wrapper);
        });

        // Add select all / clear all buttons
        const controlsDiv = document.createElement('div');
        controlsDiv.className = 'multi-select-controls';

        const selectAllBtn = document.createElement('button');
        selectAllBtn.type = 'button';
        selectAllBtn.textContent = 'Select All';
        selectAllBtn.className = 'select-all-btn';
        selectAllBtn.addEventListener('click', () => {
            container.querySelectorAll('input[type="checkbox"]').forEach(cb => {
                cb.checked = true;
                selectedValues.add(cb.value);
            });
            updateHiddenInput();
        });

        const clearAllBtn = document.createElement('button');
        clearAllBtn.type = 'button';
        clearAllBtn.textContent = 'Clear All';
        clearAllBtn.className = 'clear-all-btn';
        clearAllBtn.addEventListener('click', () => {
            container.querySelectorAll('input[type="checkbox"]').forEach(cb => {
                cb.checked = false;
            });
            selectedValues.clear();
            updateHiddenInput();
        });

        controlsDiv.appendChild(selectAllBtn);
        controlsDiv.appendChild(clearAllBtn);

        container.appendChild(controlsDiv);
        container.appendChild(hiddenInput);

        updateHiddenInput();

        // Return the hidden input but attach the container as a wrapper
        hiddenInput._wrapper = container;
        return hiddenInput;
    }

    function setupDragAndDrop(input, fieldName, sequenceType) {
        const wrapper = input._wrapper || input.parentNode;
        if (!wrapper) {
            console.warn('No wrapper found for drag and drop setup');
            return;
        }
        wrapper.classList.add('drop-zone');

        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }

        function highlight(e) {
            wrapper.classList.add('dragover');
        }

        function unhighlight(e) {
            wrapper.classList.remove('dragover');
        }

        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            wrapper.addEventListener(eventName, preventDefaults, false);
        });

        ['dragenter', 'dragover'].forEach(eventName => {
            wrapper.addEventListener(eventName, highlight, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            wrapper.addEventListener(eventName, unhighlight, false);
        });

        wrapper.addEventListener('drop', handleDrop, false);

        function handleDrop(e) {
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                const file = files[0];
                const reader = new FileReader();

                reader.onload = (e) => {
                    let content = e.target.result;

                    // Process different file types
                    if (fieldName.includes('sequence') && file.name.endsWith('.fasta')) {
                        content = parseFastaSequence(content);
                    } else if (fieldName.includes('pdb') && file.name.endsWith('.pdb')) {
                        // PDB files can be used as-is
                    } else if (file.name.endsWith('.txt')) {
                        // Text files can be used as-is
                    }

                    input.value = content;
                    input.dispatchEvent(new Event('input')); // Trigger validation and counter update
                };

                reader.readAsText(file);
            }
        }
    }

    function parseFastaSequence(fastaContent) {
        // Simple FASTA parser - extracts the first sequence
        const lines = fastaContent.split('\n');
        let sequence = '';
        let inSequence = false;

        for (const line of lines) {
            if (line.startsWith('>')) {
                if (inSequence) break; // Stop at second header (take only first sequence)
                inSequence = true;
            } else if (inSequence) {
                sequence += line.trim();
            }
        }

        return sequence || fastaContent; // Return original if no FASTA format detected
    }

    function createNestedModelField(fieldName, details) {
        const fieldset = document.createElement('fieldset');
        fieldset.className = 'nested-model-field';

        const legend = document.createElement('legend');
        legend.textContent = fieldName.replace(/([A-Z])/g, ' $1').trim();
        fieldset.appendChild(legend);

        // Create a hidden input to collect all nested field values
        const hiddenInput = document.createElement('input');
        hiddenInput.type = 'hidden';
        hiddenInput.name = fieldName;

        const nestedValues = {};

        function updateHiddenInput() {
            hiddenInput.value = JSON.stringify(nestedValues);
        }

        // Create fields for nested model
        Object.entries(details.nested_fields || {}).forEach(([nestedName, nestedDetails]) => {
            const nestedGroup = document.createElement('div');
            nestedGroup.className = 'nested-field-group';

            const nestedLabel = document.createElement('label');
            nestedLabel.textContent = nestedName;
            nestedGroup.appendChild(nestedLabel);

            let nestedInput;

            // Create appropriate input type for nested field
            if (nestedDetails.enum && nestedDetails.is_multi_select) {
                nestedInput = createMultiSelectEnum(`${fieldName}.${nestedName}`, nestedDetails);
            } else if (nestedDetails.enum) {
                nestedInput = document.createElement('select');
                nestedDetails.enum.forEach(val => {
                    const option = document.createElement('option');
                    option.value = val;
                    option.textContent = val;
                    nestedInput.appendChild(option);
                });
            } else if (nestedDetails.type.includes('int') || nestedDetails.type.includes('float')) {
                nestedInput = document.createElement('input');
                nestedInput.type = 'number';
                if (nestedDetails.ge !== null) nestedInput.min = nestedDetails.ge;
                if (nestedDetails.le !== null) nestedInput.max = nestedDetails.le;
            } else if (nestedDetails.type.includes('bool')) {
                nestedInput = document.createElement('select');
                ['true', 'false'].forEach(val => {
                    const option = document.createElement('option');
                    option.value = val;
                    option.textContent = val;
                    nestedInput.appendChild(option);
                });
            } else {
                if ((nestedName.toLowerCase().includes('sequence') || nestedName.toLowerCase().includes('pdb')) &&
                    (nestedDetails.max_length === null || nestedDetails.max_length > 50)) {
                    nestedInput = createBioSequenceInput(nestedName, nestedDetails);
                } else {
                    nestedInput = document.createElement('input');
                    nestedInput.type = 'text';
                    if (nestedDetails.min_length !== null) nestedInput.minLength = nestedDetails.min_length;
                    if (nestedDetails.max_length !== null) nestedInput.maxLength = nestedDetails.max_length;
                }
            }

            // Set default values
            if (nestedDetails.default !== null) {
                nestedInput.value = nestedDetails.default;
                nestedValues[nestedName] = nestedDetails.default;
            }

            // Add change listener to update nested values
            nestedInput.addEventListener('input', () => {
                let value = nestedInput.value;

                // Parse JSON for multi-select fields
                try {
                    const parsed = JSON.parse(value);
                    value = parsed;
                } catch {
                    // Use as-is for non-JSON values
                }

                // Type conversion
                if (nestedDetails.type.includes('int') || nestedDetails.type.includes('float')) {
                    value = Number(value);
                } else if (nestedDetails.type.includes('bool')) {
                    value = value === 'true';
                }

                nestedValues[nestedName] = value;
                updateHiddenInput();
            });

            nestedInput.addEventListener('change', () => {
                nestedInput.dispatchEvent(new Event('input'));
            });

            if (nestedInput._wrapper) {
                nestedGroup.appendChild(nestedInput._wrapper);
            } else {
                nestedGroup.appendChild(nestedInput);
            }

            if (nestedDetails.description) {
                const small = document.createElement('small');
                small.textContent = nestedDetails.description;
                nestedGroup.appendChild(small);
            }

            // Add validation hints for nested fields
            if (nestedDetails.validation_hints && nestedDetails.validation_hints.length > 0) {
                const hintsDiv = document.createElement('div');
                hintsDiv.className = 'validation-hints';

                nestedDetails.validation_hints.forEach(hint => {
                    const hintSpan = document.createElement('span');
                    hintSpan.className = 'validation-hint';
                    hintSpan.textContent = `💡 ${hint}`;
                    hintsDiv.appendChild(hintSpan);
                });

                nestedGroup.appendChild(hintsDiv);
            }

            fieldset.appendChild(nestedGroup);
        });

        fieldset.appendChild(hiddenInput);
        updateHiddenInput();

        // Return the hidden input but attach the fieldset as a wrapper
        hiddenInput._wrapper = fieldset;
        return hiddenInput;
    }

    function createItem() {
        if (!schema.items || !schema.items.properties) {
            console.error('Cannot create item: no items schema found');
            return;
        }

        const itemIndex = itemCounter++;
        const itemDiv = document.createElement('div');
        itemDiv.className = 'item';
        itemDiv.dataset.index = itemIndex;

        const itemSchema = schema.items.properties;
        for (const fieldName in itemSchema) {
            createField(fieldName, itemSchema[fieldName], itemDiv, itemIndex);
        }

        const removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.textContent = '- Remove Item';
        removeBtn.className = 'remove-item-btn';
        removeBtn.addEventListener('click', () => itemDiv.remove());

        const controls = document.createElement('div');
        controls.className = 'item-controls';
        controls.appendChild(removeBtn);
        itemDiv.appendChild(controls);

        itemsContainer.appendChild(itemDiv);
    }

    // Process schema structure
    let hasParameters = false;
    let hasItems = false;
    let itemsSchema = null;

    // If schema is empty, show a message
    if (!schema || Object.keys(schema).length === 0) {
        const noSchemaMsg = document.createElement('p');
        noSchemaMsg.textContent = 'No schema available for this endpoint.';
        noSchemaMsg.className = 'no-schema-message';
        paramsContainer.appendChild(noSchemaMsg);
        itemsSection.style.display = 'none';
        wireSubmit();
        return;
    }

    // Check if schema has typical request structure with params and items
    if (schema.params && typeof schema.params === 'object') {
        // Handle params - check if it's a nested model with fields
        if (schema.params.is_nested_model && schema.params.nested_fields) {
            hasParameters = true;
            const paramsHeader = document.createElement('h3');
            paramsHeader.textContent = 'Parameters';
            paramsContainer.appendChild(paramsHeader);

            for (const fieldName in schema.params.nested_fields) {
                createField(fieldName, schema.params.nested_fields[fieldName], paramsContainer);
            }
        } else if (schema.params.properties) {
            // Fallback for traditional properties structure
            hasParameters = true;
            const paramsHeader = document.createElement('h3');
            paramsHeader.textContent = 'Parameters';
            paramsContainer.appendChild(paramsHeader);

            for (const fieldName in schema.params.properties) {
                createField(fieldName, schema.params.properties[fieldName], paramsContainer);
            }
        }

        // Handle items if they exist - check if it's a list with nested fields
        if (schema.items && schema.items.is_list) {
            // For items that are lists of models, we need to extract the item structure
            // The type tells us it's a list, but we need to get the item model schema
            if (schema.items.nested_fields) {
                hasItems = true;
                itemsSchema = {
                    properties: schema.items.nested_fields
                };
            } else {
                // If no nested_fields but we know it's a list, create a generic text input for now
                hasItems = true;
                itemsSchema = {
                    properties: {
                        'data': {
                            type: 'str',
                            description: `Enter item data (expected type: ${schema.items.type})`,
                            default: null,
                            required: true,
                            min_length: null,
                            max_length: null,
                            enum: null,
                            is_list: false,
                            is_multi_select: false,
                            is_nested_model: false
                        }
                    }
                };
            }
        } else if (schema.items && schema.items.properties) {
            // Fallback for traditional properties structure
            hasItems = true;
            itemsSchema = schema.items;
        }
    } else {
        // Handle flattened schema structure
        for (const fieldName in schema) {
            const fieldValue = schema[fieldName];

            if (fieldValue && typeof fieldValue === 'object' && (fieldValue.type || fieldValue.properties)) {
                // This could be a regular parameter field or an items field
                if (fieldName === 'items') {
                    // This is the items field - extract its structure
                    if (fieldValue.is_list && fieldValue.nested_fields) {
                        hasItems = true;
                        itemsSchema = {
                            properties: fieldValue.nested_fields
                        };
                    }
                    // Don't create a field for items - it's handled separately
                } else {
                    // This is a regular parameter field
                    if (!hasParameters) {
                        hasParameters = true;
                        const paramsHeader = document.createElement('h3');
                        paramsHeader.textContent = 'Parameters';
                        paramsContainer.appendChild(paramsHeader);
                    }
                    createField(fieldName, fieldValue, paramsContainer);
                }
            }
        }
    }

    // If no parameters were found but we have schema fields, try treating all as
    // parameters — but EXCLUDE the 'items' field, and only add the "Parameters"
    // header if there is at least one real param field (an items-only action, e.g.
    // `predict`, must not render a dangling empty "Parameters" heading).
    if (!hasParameters) {
        const paramFieldNames = Object.keys(schema).filter(
            (fieldName) =>
                fieldName !== 'items' &&
                schema[fieldName] &&
                typeof schema[fieldName] === 'object'
        );

        if (paramFieldNames.length > 0) {
            hasParameters = true;
            const paramsHeader = document.createElement('h3');
            paramsHeader.textContent = 'Parameters';
            paramsContainer.appendChild(paramsHeader);

            paramFieldNames.forEach((fieldName) => {
                createField(fieldName, schema[fieldName], paramsContainer);
            });
        }
    }

    // If no parameters found, show a message
    if (!hasParameters) {
        const noParamsMsg = document.createElement('p');
        noParamsMsg.textContent = 'No parameters required for this endpoint.';
        noParamsMsg.className = 'no-params-message';
        paramsContainer.appendChild(noParamsMsg);
    }

    // Show/hide items section based on whether we found items schema
    if (hasItems && itemsSchema) {
        itemsSection.style.display = 'block';

        // Store items schema for createItem function
        schema.items = itemsSchema;

        createItem(); // Start with one item
        if (addItemBtn) addItemBtn.addEventListener('click', createItem);
    } else {
        itemsSection.style.display = 'none';
    }

    wireSubmit();

    function wireSubmit() {
        form.addEventListener('submit', async (event) => {
            event.preventDefault();

            const formData = new FormData(form);
            const payload = { params: {}, items: [] };
            const itemsMap = {};

            formData.forEach((value, key) => {
                const paramMatch = key.match(/^params\[(.+)\]$/);
                if (paramMatch) {
                    const paramName = paramMatch[1];
                    // An untouched optional field submits as ""; omit it so the
                    // server's own default (incl. default_factory) applies instead
                    // of failing validation on an empty value.
                    if (value === '') return;
                    // Try to parse as JSON for multi-select fields
                    try {
                        const parsed = JSON.parse(value);
                        payload.params[paramName] = parsed;
                    } catch {
                        payload.params[paramName] = value;
                    }
                    return;
                }

                const itemMatch = key.match(/^items\[(\d+)\]\[(.+)\]$/);
                if (itemMatch) {
                    const index = itemMatch[1];
                    const field = itemMatch[2];
                    if (!itemsMap[index]) itemsMap[index] = {};
                    // Try to parse as JSON for multi-select fields
                    try {
                        const parsed = JSON.parse(value);
                        itemsMap[index][field] = parsed;
                    } catch {
                        itemsMap[index][field] = value;
                    }
                }
            });

            payload.items = Object.values(itemsMap);

            // Type conversion for params
            if (schema.params && schema.params.properties) {
                Object.keys(payload.params).forEach(key => {
                    const schemaInfo = schema.params.properties[key];
                    if (schemaInfo && schemaInfo.type) {
                        if (schemaInfo.type.includes('int') || schemaInfo.type.includes('float')) {
                            payload.params[key] = Number(payload.params[key]);
                        } else if (schemaInfo.type.includes('bool')) {
                            payload.params[key] = payload.params[key] === 'true';
                        }
                    }
                });
            } else {
                // Handle flattened schema structure
                Object.keys(payload.params).forEach(key => {
                    const schemaInfo = schema[key];
                    if (schemaInfo && schemaInfo.type) {
                        if (schemaInfo.type.includes('int') || schemaInfo.type.includes('float')) {
                            payload.params[key] = Number(payload.params[key]);
                        } else if (schemaInfo.type.includes('bool')) {
                            payload.params[key] = payload.params[key] === 'true';
                        }
                    }
                });
            }

            // Type conversion for items
            if (schema.items && schema.items.properties) {
                payload.items.forEach(item => {
                    Object.keys(item).forEach(key => {
                        const schemaInfo = schema.items.properties[key];
                        if (schemaInfo && schemaInfo.type) {
                            if (schemaInfo.type.includes('int') || schemaInfo.type.includes('float')) {
                                item[key] = Number(item[key]);
                            } else if (schemaInfo.type.includes('bool')) {
                                item[key] = item[key] === 'true';
                            }
                        }
                    });
                });
            }

            if (responseArea) responseArea.className = 'response-area loading';
            if (responseCode) responseCode.textContent = 'Sending request...';

            try {
                const response = await fetch(form.dataset.endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                });

                const result = await response.json();

                if (response.ok) {
                    if (responseArea) responseArea.className = 'response-area success';
                    if (responseCode) responseCode.textContent = JSON.stringify(result, null, 2);
                } else {
                    if (responseArea) responseArea.className = 'response-area error';

                    // Handle validation errors
                    if (result && result.detail && Array.isArray(result.detail)) {
                        handleFieldValidationErrors(result.detail);
                        if (responseCode) responseCode.textContent = JSON.stringify(result, null, 2);
                    } else if (responseCode) {
                        responseCode.textContent = JSON.stringify(result, null, 2) || `HTTP Error: ${response.status}`;
                    }
                }

            } catch (error) {
                if (responseArea) responseArea.className = 'response-area error';
                if (responseCode) responseCode.textContent = `Network or parsing error: ${error.message}`;
            }
        });
    }

    // Map a FastAPI 422 `loc` (e.g. ["body","params","sequence"] or
    // ["body","items",0,"sequence"]) to the input's `name` attribute so the error
    // lands on the right field within THIS form.
    function locToName(loc) {
        if (!Array.isArray(loc) || loc.length === 0) return null;
        const parts = loc.slice();
        if (parts[0] === 'body') parts.shift();
        if (parts[0] === 'params' && parts.length >= 2) return `params[${parts[1]}]`;
        if (parts[0] === 'items' && parts.length >= 3) return `items[${parts[1]}][${parts[2]}]`;
        return null;
    }

    // Field validation error handling (scoped to this form)
    function handleFieldValidationErrors(errors) {
        // Clear previous errors on this form only
        form.querySelectorAll('.field-error').forEach(el => el.remove());
        form.querySelectorAll('.error-state').forEach(el => el.classList.remove('error-state'));

        errors.forEach(error => {
            if (!error.loc || error.loc.length === 0) return;

            let input = null;
            const name = locToName(error.loc);
            if (name) input = form.querySelector(`[name="${name}"]`);

            if (!input) {
                // Fallback: best-effort match on the joined loc path.
                const fieldPath = error.loc.join('.');
                input = form.querySelector(`[name="${fieldPath}"]`) ||
                        form.querySelector(`[name*="${fieldPath}"]`) ||
                        form.querySelector(`[id*="${fieldPath}"]`);
            }

            if (input) {
                showFieldError(input, error.msg);
            }
        });
    }

    function showFieldError(input, message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'field-error';
        errorDiv.textContent = message;

        const formGroup = input.closest('.form-group');
        if (formGroup) {
            formGroup.appendChild(errorDiv);
        } else {
            input.parentNode.appendChild(errorDiv);
        }

        input.classList.add('error-state');

        // Remove error on input change
        const removeError = () => {
            if (errorDiv.parentNode) {
                errorDiv.remove();
            }
            input.classList.remove('error-state');
            input.removeEventListener('input', removeError);
            input.removeEventListener('change', removeError);
        };

        input.addEventListener('input', removeError);
        input.addEventListener('change', removeError);
    }
}
