document.addEventListener('DOMContentLoaded', () => {
    // DOM elements
    const form = document.getElementById('playlistForm');
    const loadingState = document.getElementById('loadingState');
    const results = document.getElementById('results');
    const playlistName = document.getElementById('playlistName');
    const tracksList = document.getElementById('tracksList');
    const trackCount = document.getElementById('trackCount');
    const plexLink = document.getElementById('plexLink');
    const errorMessage = document.getElementById('errorMessage');
    const errorText = document.getElementById('errorText');
    const dismissError = document.getElementById('dismissError');

    // Model selection handling (options provided by server config)
    const modelSelect = document.getElementById('modelSelect');
    const modelSelectorWrapper = document.getElementById('modelSelectorWrapper');
    const availableModels = Array.isArray(window.availableModels) ? window.availableModels : [];
    const defaultModel = window.defaultModel || availableModels[0] || 'gpt-4';

    if (modelSelect) {
        availableModels.forEach(model => {
            const option = document.createElement('option');
            option.value = model;
            option.textContent = model;
            if (model === defaultModel) {
                option.selected = true;
            }
            modelSelect.appendChild(option);
        });
        // Only surface the selector when there's an actual choice to make.
        if (availableModels.length > 1 && modelSelectorWrapper) {
            modelSelectorWrapper.classList.remove('hidden');
        }
    }

    // Playlist length handling
    const lengthButtons = document.querySelectorAll('.playlist-length-btn');
    let selectedLength = 'medium'; // Default length

    const lengthConfigs = {
        short: { min: 20, max: 40 },
        medium: { min: 50, max: 70 },
        long: { min: 100, max: 140 }
    };

    function setActiveLength(length) {
        selectedLength = length;
        lengthButtons.forEach(btn => {
            const isActive = btn.dataset.length === length;
            // Reset all buttons first
            btn.classList.remove('border-plexorange', 'border-gray-300', 'bg-orange-50', 'dark:bg-orange-900/20', 'dark:border-gray-600');
            // Add appropriate styles
            if (isActive) {
                btn.classList.add('border-plexorange', 'bg-orange-50', 'dark:bg-orange-900/20');
            } else {
                btn.classList.add('border-gray-300', 'dark:border-gray-600');
            }
        });
    }

    // Set initial selection
    setActiveLength(selectedLength);

    // Handle button clicks
    lengthButtons.forEach(button => {
        button.addEventListener('click', () => {
            setActiveLength(button.dataset.length);
        });
    });

    // Error handling
    function showError(message) {
        // Make sure error elements exist
        if (!errorMessage || !errorText) {
            console.error('Error elements not found in DOM');
            alert(message); // Fallback to alert if error elements don't exist
            return;
        }

        errorText.textContent = message;
        errorMessage.classList.remove('hidden');
        // Scroll error into view smoothly
        errorMessage.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    function hideError() {
        if (errorMessage) {
            errorMessage.classList.add('hidden');
        }
    }

    // Add error dismiss handler if element exists
    if (dismissError) {
        dismissError.addEventListener('click', hideError);
    }

    // Handle form submission
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        // Show loading state
        loadingState.classList.remove('hidden');
        results.classList.add('hidden');
        hideError(); // Hide any previous errors

        // Get form data
        const prompt = document.getElementById('prompt').value;
        const { min, max } = lengthConfigs[selectedLength];

        try {
            const response = await fetch('/recommendations', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    prompt,
                    model: modelSelect ? modelSelect.value : defaultModel,
                    min_tracks: min,
                    max_tracks: max
                }),
            });

            let errorMessage;
            if (!response.ok) {
                const contentType = response.headers.get("content-type");
                if (contentType && contentType.includes("application/json")) {
                    const errorData = await response.json();
                    errorMessage = errorData.detail || `HTTP error! status: ${response.status}`;
                } else {
                    const textError = await response.text();
                    errorMessage = textError || `HTTP error! status: ${response.status}`;
                }
                throw new Error(errorMessage);
            }

            const data = await response.json();

            if (!data.tracks || !Array.isArray(data.tracks)) {
                throw new Error('Invalid response format: missing tracks data');
            }

            // Update UI with results
            playlistName.textContent = data.name;
            trackCount.textContent = `${data.track_count} tracks`;

            // Render tracks list
            tracksList.innerHTML = data.tracks
                .map((track, index) => `
                    <li class="py-3 flex items-center space-x-4 hover:bg-gray-50 dark:hover:bg-gray-700/50 px-4 -mx-4">
                        <span class="text-gray-400 dark:text-gray-500 w-8">${index + 1}</span>
                        <div class="min-w-0 flex-1">
                            <p class="text-sm font-medium text-gray-900 dark:text-white truncate">${track.title}</p>
                            <p class="text-sm text-gray-500 dark:text-gray-400 truncate">${track.artist}</p>
                        </div>
                    </li>
                `)
                .join('');

            // Update Plex link if ID is available
            if (data.id && data.machine_identifier) {
                plexLink.href = `https://app.plex.tv/desktop/#!/server/${data.machine_identifier}/playlist?key=/playlists/${data.id}&context=source:content.playlists`;
            }

            // Show results
            results.classList.remove('hidden');
            // Scroll results into view
            results.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

        } catch (error) {
            console.error('Error:', error);
            showError(error.message || 'Failed to generate playlist. Please try again.');
        } finally {
            loadingState.classList.add('hidden');
        }
    });
});
