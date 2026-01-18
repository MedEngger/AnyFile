document.addEventListener('DOMContentLoaded', () => {
    // Views
    const homeView = document.getElementById('home-view');
    const toolView = document.getElementById('tool-view');
    const backBtn = document.getElementById('back-btn');

    // Tool Header
    const toolTitle = document.getElementById('tool-header-title');
    const toolDesc = document.getElementById('tool-header-desc');

    // Upload Elements
    const uploadArea = document.getElementById('upload-area');
    const uploadTrigger = document.getElementById('upload-trigger');
    const fileInput = document.getElementById('file-input');
    const fileInfo = document.getElementById('file-info');
    const fileNameDisplay = document.getElementById('file-name');
    const controls = document.getElementById('controls');
    const formatSelect = document.getElementById('format-select');
    const convertBtn = document.getElementById('convert-btn');
    const progressContainer = document.getElementById('progress-container');
    const resultArea = document.getElementById('result-area');
    const downloadLink = document.getElementById('download-link');
    const errorMessage = document.getElementById('error-message');

    let currentFilename = null;
    let targetFormatOverride = null; // e.g., 'pdf' if user clicked 'Word to PDF'

    // --- Navigation Logic ---

    document.querySelectorAll('.tool-card').forEach(card => {
        card.addEventListener('click', () => {
            const tool = card.dataset.tool;
            const accept = card.dataset.accept;
            const output = card.dataset.output;
            const title = card.querySelector('.tool-title').innerText;
            const desc = card.querySelector('.tool-desc').innerText;

            enterToolMode(title, desc, accept, output);
        });
    });

    backBtn.addEventListener('click', () => {
        homeView.classList.remove('hidden');
        homeView.style.display = 'block';
        toolView.classList.remove('active');
        resetUI();
    });

    function enterToolMode(title, desc, accept, output) {
        homeView.style.display = 'none'; // Simple hide
        toolView.classList.add('active');

        toolTitle.innerText = title;
        toolDesc.innerText = desc;

        if (accept !== '*') {
            fileInput.accept = accept;
        } else {
            fileInput.removeAttribute('accept');
        }

        targetFormatOverride = (output !== 'auto') ? output : null;

        resetUI();
    }

    // --- Upload Logic (Adapted from previous version) ---

    uploadTrigger.addEventListener('click', () => fileInput.click());

    fileInput.addEventListener('change', function () {
        if (this.files.length > 0) uploadFile(this.files[0]);
    });

    // Drag & Drop
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) { e.preventDefault(); e.stopPropagation(); }

    ['dragenter', 'dragover'].forEach(eventName => {
        uploadArea.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, unhighlight, false);
    });

    function highlight(e) {
        uploadArea.classList.add('dragover');
    }

    function unhighlight(e) {
        uploadArea.classList.remove('dragover');
    }

    uploadArea.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) uploadFile(files[0]);
    });

    function uploadFile(file) {
        resetUI(false); // don't full reset, keep view

        // Show file name
        fileNameDisplay.innerText = file.name;
        fileInfo.classList.remove('hidden');
        uploadTrigger.classList.add('hidden'); // Hide big button

        const formData = new FormData();
        formData.append('file', file);

        fetch('/upload', {
            method: 'POST',
            body: formData
        })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    showError(data.error);
                    uploadTrigger.classList.remove('hidden');
                    fileInfo.classList.add('hidden');
                } else {
                    currentFilename = data.filename;
                    configureOptions(data.supported_formats);
                }
            })
            .catch(err => {
                showError("Upload failed: " + err);
                uploadTrigger.classList.remove('hidden');
                fileInfo.classList.add('hidden');
            });
    }

    function configureOptions(formats) {
        controls.classList.remove('hidden');
        formatSelect.innerHTML = '';

        if (targetFormatOverride) {
            // If the tool dictates the output (e.g., Word to PDF)
            // Verify if it's supported
            if (formats.includes(targetFormatOverride)) {
                addOption(targetFormatOverride);
                formatSelect.disabled = true; // Lock choice
            } else {
                showError(`Conversion to ${targetFormatOverride.toUpperCase()} not supported for this file.`);
                controls.classList.add('hidden');
            }
        } else {
            // Universal Mode
            formats.forEach(f => addOption(f));
            formatSelect.disabled = false;
        }
    }

    function addOption(val) {
        const opt = document.createElement('option');
        opt.value = val;
        opt.innerText = val.toUpperCase();
        formatSelect.appendChild(opt);
    }

    convertBtn.addEventListener('click', () => {
        const fmt = formatSelect.value;
        if (!currentFilename || !fmt) return;

        controls.classList.add('hidden');
        progressContainer.classList.remove('hidden');

        fetch('/convert', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename: currentFilename, format: fmt })
        })
            .then(res => res.json())
            .then(data => {
                progressContainer.classList.add('hidden');
                if (data.error) {
                    showError(data.error);
                    controls.classList.remove('hidden');
                } else {
                    resultArea.classList.remove('hidden');
                    downloadLink.href = data.download_url;
                }
            })
            .catch(err => {
                progressContainer.classList.add('hidden');
                showError(err);
            });
    });

    function showError(msg) {
        errorMessage.innerText = msg || '';
        if (msg) errorMessage.classList.remove('hidden');
        else errorMessage.classList.add('hidden');
    }

    function resetUI(full = true) {
        currentFilename = null;
        fileInput.value = '';
        errorMessage.classList.add('hidden');
        progressContainer.classList.add('hidden');
        resultArea.classList.add('hidden');
        controls.classList.add('hidden');

        if (full) {
            uploadTrigger.classList.remove('hidden');
            fileInfo.classList.add('hidden');
        }
    }
});
