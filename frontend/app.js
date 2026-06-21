const API_BASE = '/api';
let currentFile = null;
let currentTaskId = null;
let currentResults = null;
let selectedModelIndex = 0;
let chart = null;
let pollInterval = null;


document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initUpload();
    loadHistory();
});


function initTabs() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabName = btn.dataset.tab;
            
            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            document.getElementById(`${tabName}-tab`).classList.add('active');
            
            if (tabName === 'history') {
                loadHistory();
            }
        });
    });
}


function initUpload() {
    const uploadBox = document.getElementById('uploadBox');
    const fileInput = document.getElementById('fileInput');
    const selectFileBtn = document.getElementById('selectFileBtn');
    const startFitBtn = document.getElementById('startFitBtn');
    const clearFileBtn = document.getElementById('clearFileBtn');
    const refreshHistoryBtn = document.getElementById('refreshHistoryBtn');

    uploadBox.addEventListener('click', () => fileInput.click());
    selectFileBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        fileInput.click();
    });

    uploadBox.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadBox.classList.add('dragover');
    });

    uploadBox.addEventListener('dragleave', () => {
        uploadBox.classList.remove('dragover');
    });

    uploadBox.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadBox.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFile(files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFile(e.target.files[0]);
        }
    });

    startFitBtn.addEventListener('click', startFitting);
    clearFileBtn.addEventListener('click', clearFile);
    refreshHistoryBtn.addEventListener('click', loadHistory);
}


function handleFile(file) {
    if (!file.name.endsWith('.csv')) {
        alert('请选择CSV文件');
        return;
    }
    currentFile = file;
    document.getElementById('fileName').textContent = file.name;
    document.getElementById('fileInfo').style.display = 'flex';
}


function clearFile() {
    currentFile = null;
    document.getElementById('fileInput').value = '';
    document.getElementById('fileInfo').style.display = 'none';
    document.getElementById('statusSection').style.display = 'none';
    document.getElementById('resultsSection').style.display = 'none';
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }
}


async function startFitting() {
    if (!currentFile) return;

    document.getElementById('statusSection').style.display = 'block';
    document.getElementById('resultsSection').style.display = 'none';
    document.getElementById('statusTitle').textContent = '正在上传数据...';
    document.getElementById('statusDesc').textContent = '正在提交拟合任务';
    document.getElementById('spinner').style.display = 'block';

    try {
        const formData = new FormData();
        formData.append('file', currentFile);

        const response = await fetch(`${API_BASE}/fit`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || '提交失败');
        }

        currentTaskId = data.task_id;
        startPolling(currentTaskId);

    } catch (error) {
        showError(error.message);
    }
}


function startPolling(taskId) {
    if (pollInterval) clearInterval(pollInterval);
    
    document.getElementById('statusTitle').textContent = '正在拟合...';
    document.getElementById('statusDesc').textContent = '正在尝试各种微分方程形式，请稍候（高噪声数据会自动平滑处理）';

    pollInterval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE}/tasks/${taskId}`);
            const data = await response.json();

            if (data.status === 'completed') {
                clearInterval(pollInterval);
                pollInterval = null;
                loadResults(taskId);
            } else if (data.status === 'failed') {
                clearInterval(pollInterval);
                pollInterval = null;
                showError(data.error_message || '拟合失败');
            } else if (data.status === 'processing') {
                document.getElementById('statusDesc').textContent = '正在优化参数，请耐心等待...';
            }
        } catch (error) {
            console.error('Polling error:', error);
        }
    }, 2000);
}


async function loadResults(taskId) {
    try {
        const response = await fetch(`${API_BASE}/tasks/${taskId}/results`);
        const data = await response.json();

        if (data.status !== 'completed') {
            showError('任务未完成');
            return;
        }

        currentResults = data.results;
        selectedModelIndex = 0;
        
        displayResults(data);
    } catch (error) {
        showError(error.message);
    }
}


function displayResults(data) {
    document.getElementById('statusSection').style.display = 'none';
    document.getElementById('resultsSection').style.display = 'flex';

    const bestResult = data.results[0];

    displayDataQuality(bestResult);

    document.getElementById('bestEquationName').textContent = bestResult.display_name;
    renderLatex('bestEquationLatex', bestResult.latex_equation);
    document.getElementById('bestR2').textContent = bestResult.r_squared.toFixed(4);
    document.getElementById('bestAdjR2').textContent = bestResult.adjusted_r_squared.toFixed(4);
    document.getElementById('bestComposite').textContent = bestResult.composite_score.toFixed(4);
    document.getElementById('bestConfidence').textContent = (bestResult.confidence_score * 100).toFixed(1) + '%';

    let penaltyHtml = '';
    const penalties = [];
    if (bestResult.complexity_penalty > 0.01) {
        penalties.push(`复杂度惩罚: ${(bestResult.complexity_penalty * 100).toFixed(1)}%`);
    }
    if (bestResult.noise_penalty > 0.01) {
        penalties.push(`噪声惩罚: ${(bestResult.noise_penalty * 100).toFixed(1)}%`);
    }
    if (bestResult.stability_penalty > 0.01) {
        penalties.push(`稳定性惩罚: ${(bestResult.stability_penalty * 100).toFixed(1)}%`);
    }
    if (!bestResult.is_stable) {
        penalties.push(`⚠️ 数值不稳定: ${bestResult.stability_message || '未知原因'}`);
    }
    if (penalties.length > 0) {
        penaltyHtml = '💡 ' + penalties.join(' | ');
    }
    document.getElementById('penaltyInfo').innerHTML = penaltyHtml;

    renderModelsList(data.results);
    renderModelDetail(0);
    renderChart(data.results, 0);
}


function displayDataQuality(result) {
    const noiseLevel = result.noise_level;
    const snr = result.signal_to_noise;
    const smoothMethod = result.smooth_method;
    const dataPoints = result.time_points.length;

    document.getElementById('noiseLevel').textContent = (noiseLevel * 100).toFixed(2) + '%';
    document.getElementById('snrRatio').textContent = snr.toFixed(2);
    
    const smoothNames = {
        'none': '无（原始数据）',
        'savgol_light': 'Savitzky-Golay 轻度平滑',
        'savgol_medium': 'Savitzky-Golay 中度平滑',
        'savgol_heavy': 'Savitzky-Golay + MA 强平滑'
    };
    document.getElementById('smoothMethod').textContent = smoothNames[smoothMethod] || smoothMethod;
    document.getElementById('dataPoints').textContent = dataPoints;

    const indicator = document.getElementById('noiseIndicator');
    let noiseClass, noiseText;
    if (noiseLevel < 0.02) {
        noiseClass = 'noise-low';
        noiseText = '✅ 噪声水平很低，拟合结果可信度高';
    } else if (noiseLevel < 0.08) {
        noiseClass = 'noise-medium';
        noiseText = '⚠️ 噪声水平中等，结果仅供参考';
    } else if (noiseLevel < 0.2) {
        noiseClass = 'noise-high';
        noiseText = '⚠️ 噪声水平较高，建议先对数据进行预处理';
    } else {
        noiseClass = 'noise-very-high';
        noiseText = '❌ 噪声水平非常高，拟合结果可能不可靠';
    }
    indicator.className = 'noise-indicator ' + noiseClass;
    indicator.textContent = noiseText;
}


function renderModelsList(results) {
    const container = document.getElementById('modelsList');
    container.innerHTML = '';

    results.forEach((result, index) => {
        const item = document.createElement('div');
        item.className = `model-item ${index === 0 ? 'best' : ''} ${index === selectedModelIndex ? 'selected' : ''}`;
        
        let stabilityBadge = result.is_stable ? '' : '<span style="color:#e53e3e;font-size:0.8rem;"> ⚠️</span>';

        item.innerHTML = `
            <div class="model-rank">${index + 1}</div>
            <div class="model-info">
                <div class="model-name">${result.display_name}${stabilityBadge}</div>
                <div class="model-desc">${result.description || ''} · ${result.order}阶</div>
            </div>
            <div class="model-metrics">
                <div class="r2">R²: ${result.r_squared.toFixed(4)}</div>
                <div class="confidence">置信度: ${(result.confidence_score * 100).toFixed(1)}%</div>
                <div class="composite-score">综合: ${result.composite_score.toFixed(4)}</div>
            </div>
        `;

        item.addEventListener('click', () => {
            selectedModelIndex = index;
            renderModelsList(results);
            renderModelDetail(index);
            renderChart(results, index);
        });

        container.appendChild(item);
    });
}


function renderModelDetail(index) {
    const result = currentResults[index];
    const card = document.getElementById('modelDetailCard');
    
    card.style.display = 'block';
    document.getElementById('detailModelName').textContent = result.display_name;
    
    const stabilityBadge = document.getElementById('stabilityBadge');
    if (result.is_stable) {
        stabilityBadge.className = 'stability-badge stability-stable';
        stabilityBadge.textContent = '✓ 数值稳定';
    } else {
        stabilityBadge.className = 'stability-badge stability-unstable';
        stabilityBadge.textContent = '⚠️ 数值不稳定: ' + (result.stability_message || '');
    }
    
    renderLatex('detailEquationLatex', result.latex_equation);
    
    document.getElementById('detailR2').textContent = result.r_squared.toFixed(4);
    document.getElementById('detailAdjR2').textContent = result.adjusted_r_squared.toFixed(4);
    document.getElementById('detailNrmse').textContent = (result.normalized_rmse * 100).toFixed(2) + '%';
    document.getElementById('detailAicc').textContent = result.aic_c.toFixed(2);
    document.getElementById('detailBic').textContent = result.bic.toFixed(2);
    document.getElementById('detailConfidence').textContent = (result.confidence_score * 100).toFixed(1) + '%';

    document.getElementById('penaltyComplexity').textContent = (result.complexity_penalty * 100).toFixed(2) + '%';
    document.getElementById('penaltyNoise').textContent = (result.noise_penalty * 100).toFixed(2) + '%';
    document.getElementById('penaltyStability').textContent = (result.stability_penalty * 100).toFixed(2) + '%';

    const paramsGrid = document.getElementById('detailParams');
    paramsGrid.innerHTML = '';

    const paramsTitle = document.createElement('div');
    paramsTitle.style.cssText = 'grid-column: 1/-1; font-weight: 600; color: #2d3748; margin-bottom: 5px;';
    paramsTitle.textContent = '模型参数';
    paramsGrid.appendChild(paramsTitle);

    for (const [name, value] of Object.entries(result.params)) {
        const paramItem = document.createElement('div');
        paramItem.className = 'param-item';
        paramItem.innerHTML = `
            <span class="param-name">${name}</span>
            <span class="param-value">${value.toFixed(4)}</span>
        `;
        paramsGrid.appendChild(paramItem);
    }

    const x0Title = document.createElement('div');
    x0Title.style.cssText = 'grid-column: 1/-1; font-weight: 600; color: #2d3748; margin-top: 10px; margin-bottom: 5px;';
    x0Title.textContent = '初始条件';
    paramsGrid.appendChild(x0Title);

    result.x0.forEach((val, i) => {
        const paramItem = document.createElement('div');
        paramItem.className = 'param-item';
        const label = result.order === 2 ? (i === 0 ? 'x₀' : 'dx₀/dt') : 'x₀';
        paramItem.innerHTML = `
            <span class="param-name">${label}</span>
            <span class="param-value">${val.toFixed(4)}</span>
        `;
        paramsGrid.appendChild(paramItem);
    });
}


function renderChart(results, selectedIndex) {
    const ctx = document.getElementById('fitChart').getContext('2d');
    const result = results[selectedIndex];

    if (chart) {
        chart.destroy();
    }

    const datasets = [];

    datasets.push({
        label: '原始数据',
        data: result.original_data,
        borderColor: '#cbd5e0',
        backgroundColor: 'rgba(203, 213, 224, 0.1)',
        pointRadius: 3,
        pointHoverRadius: 5,
        tension: 0,
        borderWidth: 1,
        fill: false,
        pointStyle: 'circle'
    });

    if (result.smoothed_data && result.smooth_method !== 'none') {
        datasets.push({
            label: '平滑后数据',
            data: result.smoothed_data,
            borderColor: '#667eea',
            backgroundColor: 'rgba(102, 126, 234, 0.1)',
            pointRadius: 0,
            tension: 0.3,
            borderWidth: 2,
            fill: false,
            borderDash: []
        });
    }

    datasets.push({
        label: '拟合曲线',
        data: result.fitted_curve,
        borderColor: '#48bb78',
        backgroundColor: 'rgba(72, 187, 120, 0.15)',
        pointRadius: 0,
        tension: 0.3,
        borderWidth: 3,
        fill: false
    });

    chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: result.time_points,
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        usePointStyle: true,
                        padding: 20
                    }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false
                }
            },
            scales: {
                x: {
                    type: 'linear',
                    title: {
                        display: true,
                        text: '时间 (t)'
                    },
                    grid: {
                        color: 'rgba(0,0,0,0.05)'
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: 'x(t)'
                    },
                    grid: {
                        color: 'rgba(0,0,0,0.05)'
                    }
                }
            },
            interaction: {
                mode: 'nearest',
                axis: 'x',
                intersect: false
            }
        }
    });

    const canvas = document.getElementById('fitChart');
    canvas.style.height = '380px';
}


function renderLatex(elementId, latex) {
    const element = document.getElementById(elementId);
    try {
        katex.render(latex, element, {
            throwOnError: false,
            displayMode: true
        });
    } catch (e) {
        element.textContent = latex;
    }
}


function showError(message) {
    document.getElementById('statusSection').style.display = 'block';
    document.getElementById('resultsSection').style.display = 'none';
    document.getElementById('spinner').style.display = 'none';
    document.getElementById('statusTitle').textContent = '❌ 出错了';
    document.getElementById('statusDesc').textContent = message;
}


async function loadHistory() {
    const container = document.getElementById('historyList');
    
    try {
        const response = await fetch(`${API_BASE}/tasks?limit=50`);
        const data = await response.json();

        if (data.tasks.length === 0) {
            container.innerHTML = '<p class="empty-hint">暂无历史任务</p>';
            return;
        }

        container.innerHTML = '';

        data.tasks.forEach(task => {
            const item = document.createElement('div');
            item.className = 'history-item';
            
            const statusClass = `status-${task.status}`;
            const statusText = {
                'pending': '排队中',
                'processing': '处理中',
                'completed': '已完成',
                'failed': '失败'
            }[task.status] || task.status;

            const date = new Date(task.created_at).toLocaleString('zh-CN');

            let detailHtml = '';
            if (task.status === 'completed' && task.best_equation) {
                detailHtml = `
                    <div class="history-detail">
                        <div class="history-equation">${task.best_equation}</div>
                        <div class="history-r2">R²: ${task.best_r_squared ? task.best_r_squared.toFixed(4) : 'N/A'} · 置信度: ${task.confidence_score ? (task.confidence_score * 100).toFixed(1) + '%' : 'N/A'}</div>
                    </div>
                `;
            }

            item.innerHTML = `
                <span class="history-status ${statusClass}">${statusText}</span>
                <div class="history-info">
                    <div class="history-filename">${task.filename}</div>
                    <div class="history-date">${date} · ${task.data_points} 个数据点</div>
                </div>
                ${detailHtml}
            `;

            item.addEventListener('click', () => {
                if (task.status === 'completed') {
                    viewHistoryTask(task.id);
                }
            });

            container.appendChild(item);
        });

    } catch (error) {
        container.innerHTML = `<p class="empty-hint">加载失败: ${error.message}</p>`;
    }
}


function viewHistoryTask(taskId) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelector('[data-tab="fit"]').classList.add('active');
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.getElementById('fit-tab').classList.add('active');

    document.getElementById('statusSection').style.display = 'block';
    document.getElementById('resultsSection').style.display = 'none';
    document.getElementById('spinner').style.display = 'block';
    document.getElementById('statusTitle').textContent = '加载中...';
    document.getElementById('statusDesc').textContent = '正在加载历史任务结果';

    currentTaskId = taskId;
    loadResults(taskId);
}
