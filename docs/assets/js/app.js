let allItems = [];
let categories = [];
let filteredItems = [];
let currentPage = 1;
const itemsPerPage = 30;

let activeFilters = new Set();
let searchQuery = '';
let dateFilter = 'all';
let sortOrder = 'desc';
let showMuted = false;

// Elements
const itemsContainer = document.getElementById('items-container');
const categoryFiltersContainer = document.getElementById('category-filters');
const resultCountEl = document.getElementById('result-count');
const searchInput = document.getElementById('search-input');
const dateFilterSelect = document.getElementById('date-filter');
const sortFilterSelect = document.getElementById('sort-filter');
const paginationContainer = document.getElementById('pagination');
const loadingIndicator = document.getElementById('loading-indicator');

// Charts
let categoryChartInstance = null;
let timelineChartInstance = null;

// Modal Elements
let categoryModal, modalCategoryList, manageCategoriesBtn, closeModalBtn, modalOverlay, addCategoryBtn, downloadCategoriesBtn, copyCategoriesBtn;

// Initialization
async function init() {
    setupThemeToggle();
    try {
        const [archiveRes, categoriesRes] = await Promise.all([
            fetch('data/archive.json').then(r => r.json()).catch(() => ({ items: [] })),
            fetch('data/categories.json').then(r => r.json()).catch(() => ({ categories: [] }))
        ]);
        
        allItems = archiveRes.items || [];
        categories = categoriesRes.categories || [];
        
        document.getElementById('total-count').textContent = allItems.length.toLocaleString();
        if(archiveRes.last_updated) {
            const d = new Date(archiveRes.last_updated);
            document.getElementById('last-updated').textContent = `업데이트: ${d.toLocaleString()}`;
        }

        renderCategoryFilters();
        setupEventListeners();
        applyFilters();
        
    } catch (error) {
        console.error("Error loading data:", error);
        loadingIndicator.innerHTML = '<p class="text-red-500">데이터를 불러오는데 실패했습니다.</p>';
    }
}

function setupThemeToggle() {
    const themeToggle = document.getElementById('theme-toggle');
    const html = document.documentElement;
    const icon = themeToggle.querySelector('i');

    const updateIcon = () => {
        if (html.classList.contains('dark')) {
            icon.setAttribute('data-lucide', 'sun');
        } else {
            icon.setAttribute('data-lucide', 'moon');
        }
        lucide.createIcons();
    };

    if (localStorage.theme === 'dark' || (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
        html.classList.add('dark');
    } else {
        html.classList.remove('dark');
    }
    updateIcon();

    themeToggle.addEventListener('click', () => {
        html.classList.toggle('dark');
        if (html.classList.contains('dark')) {
            localStorage.theme = 'dark';
        } else {
            localStorage.theme = 'light';
        }
        updateIcon();
        updateChartsTheme();
    });
}

function renderCategoryFilters() {
    categoryFiltersContainer.innerHTML = '';
    
    // Total button
    const totalBtn = document.createElement('button');
    totalBtn.className = `chip-transition px-3 py-1.5 rounded-full text-xs font-medium border border-gray-200 dark:border-gray-600 bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200`;
    totalBtn.textContent = '전체';
    totalBtn.onclick = () => {
        activeFilters.clear();
        updateFilterStyles();
        applyFilters();
    };
    categoryFiltersContainer.appendChild(totalBtn);

    categories.forEach(cat => {
        const btn = document.createElement('button');
        btn.className = `category-btn chip-transition px-3 py-1.5 rounded-full text-xs font-medium border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700`;
        btn.dataset.label = cat.label;
        btn.dataset.color = cat.color;
        
        btn.innerHTML = `<span class="inline-block w-2 h-2 rounded-full mr-1.5" style="background-color: ${cat.color}"></span>${cat.label}`;
        
        btn.onclick = () => {
            if (activeFilters.has(cat.label)) {
                activeFilters.delete(cat.label);
            } else {
                activeFilters.add(cat.label);
            }
            updateFilterStyles();
            applyFilters();
        };
        categoryFiltersContainer.appendChild(btn);
    });
}

function updateFilterStyles() {
    const btns = document.querySelectorAll('.category-btn');
    btns.forEach(btn => {
        const label = btn.dataset.label;
        const color = btn.dataset.color;
        if (activeFilters.has(label)) {
            btn.style.borderColor = color;
            btn.style.backgroundColor = `${color}15`;
        } else {
            btn.style.borderColor = '';
            btn.style.backgroundColor = '';
        }
    });
}

function setupEventListeners() {
    // Initialize elements
    categoryModal = document.getElementById('category-modal');
    modalCategoryList = document.getElementById('modal-category-list');
    manageCategoriesBtn = document.getElementById('manage-categories-btn');
    closeModalBtn = document.getElementById('close-modal');
    modalOverlay = document.getElementById('modal-overlay');
    addCategoryBtn = document.getElementById('add-category-btn');
    downloadCategoriesBtn = document.getElementById('download-categories');
    copyCategoriesBtn = document.getElementById('copy-categories');

    let debounceTimer;
    searchInput.addEventListener('input', (e) => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            searchQuery = e.target.value.toLowerCase();
            applyFilters();
        }, 300);
    });

    dateFilterSelect.addEventListener('change', (e) => {
        dateFilter = e.target.value;
        applyFilters();
    });

    sortFilterSelect.addEventListener('change', (e) => {
        sortOrder = e.target.value;
        applyFilters();
    });

    const showMutedCheckbox = document.getElementById('show-muted');
    if (showMutedCheckbox) showMutedCheckbox.addEventListener('change', (e) => {
        showMuted = e.target.checked;
        applyFilters();
    });

    document.getElementById('download-csv').addEventListener('click', downloadCSV);
    
    // Category Management Modal
    if (manageCategoriesBtn) manageCategoriesBtn.addEventListener('click', openCategoryModal);
    if (closeModalBtn) closeModalBtn.addEventListener('click', closeCategoryModal);
    if (modalOverlay) modalOverlay.addEventListener('click', closeCategoryModal);
    if (addCategoryBtn) addCategoryBtn.addEventListener('click', addNewCategory);
    if (downloadCategoriesBtn) downloadCategoriesBtn.addEventListener('click', downloadCategoriesJson);
    if (copyCategoriesBtn) copyCategoriesBtn.addEventListener('click', copyCategoriesJson);
}

function openCategoryModal() {
    categoryModal.classList.remove('hidden');
    renderModalCategoryList();
}

function closeCategoryModal() {
    categoryModal.classList.add('hidden');
}

function renderModalCategoryList() {
    modalCategoryList.innerHTML = '';
    categories.forEach((cat, index) => {
        const item = document.createElement('div');
        item.className = 'p-4 bg-gray-50 dark:bg-gray-700/50 rounded-xl border border-gray-100 dark:border-gray-600 space-y-3';
        item.innerHTML = `
            <div class="flex items-center justify-between gap-4">
                <div class="flex-1 grid grid-cols-2 gap-3">
                    <div>
                        <label class="block text-[10px] uppercase tracking-wider text-gray-400 mb-1 font-bold">카테고리명</label>
                        <input type="text" value="${cat.label}" onchange="updateCategory(${index}, 'label', this.value)" 
                            class="w-full px-3 py-1.5 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-lg text-sm outline-none focus:ring-1 focus:ring-blue-500">
                    </div>
                    <div>
                        <label class="block text-[10px] uppercase tracking-wider text-gray-400 mb-1 font-bold">색상 (HEX)</label>
                        <div class="flex gap-2">
                            <input type="color" value="${cat.color}" onchange="updateCategory(${index}, 'color', this.value)" class="h-8 w-8 rounded cursor-pointer border-none p-0 bg-transparent">
                            <input type="text" value="${cat.color}" onchange="updateCategory(${index}, 'color', this.value)" 
                                class="flex-1 px-3 py-1.5 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-lg text-xs outline-none focus:ring-1 focus:ring-blue-500 font-mono">
                        </div>
                    </div>
                </div>
                <button onclick="deleteCategory(${index})" class="mt-4 p-2 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors" title="삭제">
                    <i data-lucide="trash-2" class="w-5 h-5"></i>
                </button>
            </div>
            <div>
                <label class="block text-[10px] uppercase tracking-wider text-gray-400 mb-1 font-bold">키워드 (쉼표로 구분)</label>
                <input type="text" value="${cat.keywords.join(', ')}" onchange="updateCategory(${index}, 'keywords', this.value)" 
                    class="w-full px-3 py-1.5 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-lg text-xs outline-none focus:ring-1 focus:ring-blue-500"
                    placeholder="예: 수소, H2, 수소경제">
            </div>
        `;
        modalCategoryList.appendChild(item);
    });
    lucide.createIcons();
}

window.updateCategory = (index, field, value) => {
    if (field === 'keywords') {
        categories[index][field] = value.split(',').map(s => s.trim()).filter(s => s !== '');
    } else {
        categories[index][field] = value;
    }
    // Refresh main UI
    renderCategoryFilters();
    updateFilterStyles();
};

window.deleteCategory = (index) => {
    if (confirm('정말 이 카테고리를 삭제할까요?')) {
        categories.splice(index, 1);
        renderModalCategoryList();
        renderCategoryFilters();
        applyFilters();
    }
};

function addNewCategory() {
    const newId = 'cat_' + Date.now();
    categories.push({
        id: newId,
        label: '새 카테고리',
        color: '#3B82F6',
        keywords: []
    });
    renderModalCategoryList();
    renderCategoryFilters();
}

function downloadCategoriesJson() {
    const jsonString = generateCategoriesJson();
    const blob = new Blob([jsonString], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'categories.json';
    link.click();
    URL.revokeObjectURL(url);
}

function copyCategoriesJson() {
    const jsonString = generateCategoriesJson();
    navigator.clipboard.writeText(jsonString).then(() => {
        const originalText = copyCategoriesBtn.innerHTML;
        copyCategoriesBtn.innerHTML = '<i data-lucide="check" class="w-5 h-5"></i> 복사 완료!';
        copyCategoriesBtn.classList.replace('bg-blue-600', 'bg-green-600');
        lucide.createIcons();
        setTimeout(() => {
            copyCategoriesBtn.innerHTML = originalText;
            copyCategoriesBtn.classList.replace('bg-green-600', 'bg-blue-600');
            lucide.createIcons();
        }, 2000);
    });
}

function generateCategoriesJson() {
    const data = {
        version: "1.0",
        updated_at: new Date().toISOString().split('T')[0],
        categories: categories,
        matching_rule: {
            fields: ["title", "description"],
            case_sensitive: false,
            multi_match: true
        }
    };
    return JSON.stringify(data, null, 2);
}

function applyFilters() {
    let result = allItems;

    // 중복 병합: 원본만 표시 (score.py가 dup_of 표시)
    result = result.filter(item => !item.dup_of);

    // 숨김(Mute) 처리 — mute_rules.json 기준, 토글로 표시 가능
    const mutedInScope = result.filter(item => item.muted).length;
    const mutedCountEl = document.getElementById('muted-count');
    if (mutedCountEl) mutedCountEl.textContent = mutedInScope > 0 ? `(${mutedInScope}건)` : '';
    if (!showMuted) {
        result = result.filter(item => !item.muted);
    }

    // Category filter (OR matching for selected categories)
    if (activeFilters.size > 0) {
        result = result.filter(item => {
            if (!item.matched_categories || item.matched_categories.length === 0) return false;
            return item.matched_categories.some(cat => activeFilters.has(cat));
        });
    }

    // Search filter
    if (searchQuery) {
        result = result.filter(item => 
            (item.title && item.title.toLowerCase().includes(searchQuery)) ||
            (item.description && item.description.toLowerCase().includes(searchQuery))
        );
    }

    // Date filter
    if (dateFilter !== 'all') {
        const now = new Date();
        const past = new Date();
        if (dateFilter === '7d') past.setDate(now.getDate() - 7);
        if (dateFilter === '30d') past.setDate(now.getDate() - 30);
        if (dateFilter === '1y') past.setFullYear(now.getFullYear() - 1);
        
        result = result.filter(item => {
            const date = new Date(item.pub_date || item.collected_at);
            return date >= past;
        });
    }

    // Sort
    result.sort((a, b) => {
        if (sortOrder === 'score') {
            const diff = (b.pt_score || 0) - (a.pt_score || 0);
            if (diff !== 0) return diff;
        }
        const dateA = new Date(a.pub_date || a.collected_at);
        const dateB = new Date(b.pub_date || b.collected_at);
        return sortOrder === 'asc' ? dateA - dateB : dateB - dateA;
    });

    filteredItems = result;
    currentPage = 1;
    renderList();
    renderCharts();
}

function renderList() {
    itemsContainer.innerHTML = '';
    resultCountEl.textContent = filteredItems.length.toLocaleString();

    const start = (currentPage - 1) * itemsPerPage;
    const end = start + itemsPerPage;
    const paginatedItems = filteredItems.slice(start, end);

    if (paginatedItems.length === 0) {
        itemsContainer.innerHTML = `<tr><td colspan="7" class="text-center py-12 text-gray-500 dark:text-gray-400">조건에 맞는 결과가 없습니다.</td></tr>`;
        renderPagination();
        return;
    }

    let virtualNo = filteredItems.length - start;

    paginatedItems.forEach(item => {
        const row = document.createElement('tr');
        row.className = 'hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors group cursor-pointer' + (item.muted ? ' opacity-50' : '');
        row.onclick = (e) => {
            // Prevent opening again if a link was clicked directly
            if (e.target.tagName !== 'A') {
                window.open(item.link, '_blank', 'noopener,noreferrer');
            }
        };

        const date = new Date(item.pub_date || item.collected_at).toLocaleDateString();
        
        let categoriesHtml = '';
        if (item.matched_categories && item.matched_categories.length > 0) {
            categoriesHtml = item.matched_categories.map(catLabel => {
                const catDef = categories.find(c => c.label === catLabel);
                const color = catDef ? catDef.color : '#9ca3af';
                return `<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium whitespace-nowrap" style="background-color: ${color}15; color: ${color}; border: 1px solid ${color}30">
                    ${catLabel}
                </span>`;
            }).join(' ');
        } else {
            categoriesHtml = `<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400 whitespace-nowrap">미분류</span>`;
        }

        // 관련도 배지 (score.py가 계산한 pt_score, 근거는 툴팁)
        const score = item.pt_score || 0;
        const reasonsTip = (item.pt_reasons && item.pt_reasons.length) ? `근거: ${item.pt_reasons.join(', ')}` : '매칭된 관심 키워드 없음';
        let scoreHtml;
        if (score >= 80) {
            scoreHtml = `<span class="inline-flex items-center justify-center min-w-[38px] px-1.5 py-0.5 rounded-md text-xs font-bold bg-teal-600 text-white" title="${reasonsTip}">${score}</span>`;
        } else if (score >= 60) {
            scoreHtml = `<span class="inline-flex items-center justify-center min-w-[38px] px-1.5 py-0.5 rounded-md text-xs font-bold bg-teal-100 text-teal-800 dark:bg-teal-900/40 dark:text-teal-300" title="${reasonsTip}">${score}</span>`;
        } else if (score >= 40) {
            scoreHtml = `<span class="inline-flex items-center justify-center min-w-[38px] px-1.5 py-0.5 rounded-md text-xs font-semibold bg-gray-200 text-gray-700 dark:bg-gray-600 dark:text-gray-200" title="${reasonsTip}">${score}</span>`;
        } else {
            scoreHtml = `<span class="text-xs text-gray-400 dark:text-gray-500" title="${reasonsTip}">${score > 0 ? score : '·'}</span>`;
        }
        const mutedChip = item.muted ? `<span class="ml-1 inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400" title="mute_rules.json 패턴과 일치">숨김</span>` : '';

        row.innerHTML = `
            <td class="px-4 py-4 text-center text-gray-500 dark:text-gray-400">${virtualNo--}</td>
            <td class="px-4 py-4 text-center whitespace-nowrap">${scoreHtml}${mutedChip}</td>
            <td class="px-4 py-4 text-center">
                <div class="flex gap-1 flex-wrap justify-center">
                    ${categoriesHtml}
                </div>
            </td>
            <td class="px-4 py-4">
                <a href="${item.link}" target="_blank" rel="noopener noreferrer" class="block">
                    <span class="text-base font-medium text-gray-900 dark:text-white group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors line-clamp-1">${item.title}</span>
                </a>
            </td>
            <td class="px-4 py-4 text-center text-gray-500 dark:text-gray-400 whitespace-nowrap">${item.author || 'KDI'}</td>
            <td class="px-4 py-4 text-center text-gray-500 dark:text-gray-400 whitespace-nowrap">${date}</td>
            <td class="px-4 py-4 text-center">
                <a href="${item.link}" target="_blank" rel="noopener noreferrer" class="inline-flex items-center justify-center p-2 text-blue-600 hover:bg-blue-50 dark:text-blue-400 dark:hover:bg-blue-900/30 rounded-lg transition-colors" title="원본 페이지로 바로가기">
                    <i data-lucide="external-link" class="w-4 h-4"></i>
                </a>
            </td>
        `;
        itemsContainer.appendChild(row);
    });

    lucide.createIcons();
    renderPagination();
}

function renderPagination() {
    paginationContainer.innerHTML = '';
    const totalPages = Math.ceil(filteredItems.length / itemsPerPage);
    if (totalPages <= 1) return;

    // Prev
    const prevBtn = document.createElement('button');
    prevBtn.innerHTML = '<i data-lucide="chevron-left" class="w-4 h-4"></i>';
    prevBtn.className = `p-2 flex items-center justify-center rounded-lg border ${currentPage === 1 ? 'border-gray-200 text-gray-300 cursor-not-allowed dark:border-gray-700 dark:text-gray-600' : 'border-gray-200 text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700'}`;
    prevBtn.disabled = currentPage === 1;
    prevBtn.onclick = () => { currentPage--; renderList(); window.scrollTo({top: 0, behavior: 'smooth'}); };
    paginationContainer.appendChild(prevBtn);

    // Page numbers
    const startPage = Math.max(1, currentPage - 2);
    const endPage = Math.min(totalPages, startPage + 4);

    for (let i = startPage; i <= endPage; i++) {
        const pageBtn = document.createElement('button');
        pageBtn.textContent = i;
        pageBtn.className = `w-10 h-10 flex items-center justify-center rounded-lg text-sm font-medium ${currentPage === i ? 'bg-blue-600 text-white' : 'border border-gray-200 text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700'}`;
        pageBtn.onclick = () => { currentPage = i; renderList(); window.scrollTo({top: 0, behavior: 'smooth'}); };
        paginationContainer.appendChild(pageBtn);
    }

    // Next
    const nextBtn = document.createElement('button');
    nextBtn.innerHTML = '<i data-lucide="chevron-right" class="w-4 h-4"></i>';
    nextBtn.className = `p-2 flex items-center justify-center rounded-lg border ${currentPage === totalPages ? 'border-gray-200 text-gray-300 cursor-not-allowed dark:border-gray-700 dark:text-gray-600' : 'border-gray-200 text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700'}`;
    nextBtn.disabled = currentPage === totalPages;
    nextBtn.onclick = () => { currentPage++; renderList(); window.scrollTo({top: 0, behavior: 'smooth'}); };
    paginationContainer.appendChild(nextBtn);
    
    lucide.createIcons();
}

function renderCharts() {
    const isDark = document.documentElement.classList.contains('dark');
    const textColor = isDark ? '#9ca3af' : '#4b5563';
    const gridColor = isDark ? '#374151' : '#f3f4f6';

    // 1. Category Chart
    const catCounts = {};
    categories.forEach(c => catCounts[c.label] = 0);
    catCounts['미분류'] = 0;

    filteredItems.forEach(item => {
        if (item.matched_categories && item.matched_categories.length > 0) {
            item.matched_categories.forEach(cat => {
                if (catCounts[cat] !== undefined) catCounts[cat]++;
            });
        } else {
            catCounts['미분류']++;
        }
    });

    const catLabels = [];
    const catData = [];
    const catColors = [];

    categories.forEach(c => {
        if (catCounts[c.label] > 0) {
            catLabels.push(c.label);
            catData.push(catCounts[c.label]);
            catColors.push(c.color);
        }
    });
    if (catCounts['미분류'] > 0) {
        catLabels.push('미분류');
        catData.push(catCounts['미분류']);
        catColors.push('#9ca3af');
    }

    if (categoryChartInstance) categoryChartInstance.destroy();
    const ctx1 = document.getElementById('categoryChart').getContext('2d');
    categoryChartInstance = new Chart(ctx1, {
        type: 'doughnut',
        data: {
            labels: catLabels,
            datasets: [{
                data: catData,
                backgroundColor: catColors,
                borderWidth: isDark ? 2 : 1,
                borderColor: isDark ? '#1f2937' : '#ffffff'
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { position: 'right', labels: { color: textColor } },
                title: { display: true, text: '카테고리별 분포', color: textColor }
            }
        }
    });

    // 2. Timeline Chart
    const months = {};
    filteredItems.forEach(item => {
        const date = new Date(item.pub_date || item.collected_at);
        const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
        months[key] = (months[key] || 0) + 1;
    });

    const sortedMonths = Object.keys(months).sort();
    const timelineData = sortedMonths.map(k => months[k]);

    if (timelineChartInstance) timelineChartInstance.destroy();
    const ctx2 = document.getElementById('timelineChart').getContext('2d');
    timelineChartInstance = new Chart(ctx2, {
        type: 'line',
        data: {
            labels: sortedMonths,
            datasets: [{
                label: '발행 건수',
                data: timelineData,
                borderColor: '#3b82f6',
                backgroundColor: '#3b82f633',
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            scales: {
                x: { ticks: { color: textColor }, grid: { color: gridColor } },
                y: { ticks: { color: textColor, stepSize: 1 }, grid: { color: gridColor }, beginAtZero: true }
            },
            plugins: {
                legend: { display: false },
                title: { display: true, text: '월별 추이', color: textColor }
            }
        }
    });
}

function updateChartsTheme() {
    if(filteredItems.length > 0) {
        renderCharts();
    }
}

function downloadCSV() {
    if (filteredItems.length === 0) {
        alert("다운로드할 데이터가 없습니다.");
        return;
    }

    const headers = ['Title', 'Link', 'Date', 'Score', 'ScoreReasons', 'Categories', 'Author', 'Description'];
    const rows = filteredItems.map(item => {
        const desc = (item.description || '').replace(/"/g, '""').replace(/\n/g, ' ');
        const cats = (item.matched_categories || []).join(', ');
        const reasons = (item.pt_reasons || []).join(', ');
        const date = new Date(item.pub_date || item.collected_at).toLocaleDateString();
        return `"${item.title.replace(/"/g, '""')}","${item.link}","${date}","${item.pt_score || 0}","${reasons}","${cats}","${(item.author || '').replace(/"/g, '""')}","${desc}"`;
    });

    const csvContent = "\uFEFF" + [headers.join(','), ...rows].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `kdi_archive_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
    URL.revokeObjectURL(url);
}

// Start
init();
