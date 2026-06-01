document.addEventListener('DOMContentLoaded', function() {
    // Photo Gallery Toggle
    document.getElementById('toggle-photos-btn').addEventListener('click', function() {
        document.getElementById('photo-gallery').classList.toggle('hidden');
    });

    // Sortable Photo Grids
    const featuredGrid = document.getElementById('featured-photos');
    const otherGrid = document.getElementById('other-photos');

    const saveOrder = () => {
        const featuredIds = Array.from(featuredGrid.children).map(item => item.dataset.id);
        const otherIds = Array.from(otherGrid.children).map(item => item.dataset.id);
        const order = featuredIds.concat(otherIds);

        fetch(window.adminConfig.reorderPhotosUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ order: order })
        }).catch(err => console.error('Failed to save order:', err));
    };

    if (featuredGrid) new Sortable(featuredGrid, { animation: 150, group: 'shared', ghostClass: 'sortable-ghost', onEnd: saveOrder });
    if (otherGrid) new Sortable(otherGrid, { animation: 150, group: 'shared', ghostClass: 'sortable-ghost', onEnd: saveOrder });
});

// AJAX Photo Visibility & Featured Toggle
async function toggleVisibility(photoId, button) {
    // ... same as before
}

async function toggleFeatured(photoId, button) {
    try {
        const response = await fetch(`/admin/photo/${photoId}/toggle_featured`, { method: 'POST' });
        const data = await response.json();
        if (data.status === 'success') {
            // Instead of just toggling class, we reload to re-render the sections
            window.location.reload();
        } else { alert('Error: ' + data.message); }
    } catch (error) { console.error('Failed to toggle featured state:', error); alert('An unexpected error occurred.'); }
}

async function toggleRegistryState(checkbox) {
    const statusIndicator = document.getElementById('toggle-status-indicator');
    if (statusIndicator) {
        statusIndicator.textContent = 'Saving...';
        statusIndicator.style.opacity = '1';
    }
    
    try {
        const response = await fetch(window.adminConfig.toggleGiftRegistryUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: checkbox.checked })
        });
        const data = await response.json();
        if (data.status === 'success') {
            if (statusIndicator) {
                statusIndicator.textContent = 'Saved!';
                setTimeout(() => {
                    statusIndicator.style.opacity = '0';
                }, 1500);
            }
        } else {
            alert('Failed to save setting: ' + data.message);
            checkbox.checked = !checkbox.checked; // revert
            if (statusIndicator) statusIndicator.style.opacity = '0';
        }
    } catch (err) {
        console.error('Failed to toggle registry state:', err);
        alert('An unexpected error occurred while saving the setting.');
        checkbox.checked = !checkbox.checked; // revert
        if (statusIndicator) statusIndicator.style.opacity = '0';
    }
}

// Multi-upload and ZIP handling
// ... same as before
