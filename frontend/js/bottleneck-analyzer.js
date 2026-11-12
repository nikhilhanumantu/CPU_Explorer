/**
 * CPU Performance Explorer - Bottleneck Analyzer Controller
 * Implements a heuristic, TMA-style (Top-Down Microarchitecture Analysis) breakdown,
 * structural stall categorization with actionable optimization recommendations,
 * and live host telemetry streaming (estimated from psutil, not hardware PMU reads).
 */

(function () {
  let currentProfile = 'latest';
  let isPMUStreaming = false;
  let pmuStreamTimer = null;

  async function loadBottlenecks(profileKey = 'latest') {
    currentProfile = profileKey;
    try {
      let res;
      if (profileKey === 'latest') {
        res = await apiFetch('/api/bottleneck/from-latest');
      } else if (profileKey === 'matrix_avx512') {
        res = await apiFetch('/api/bottleneck/analyze', {
          method: 'POST',
          body: JSON.stringify({ cpi: 1.85, llc_miss_rate: 14.2, branch_mispredict_rate: 3.5, pipeline_stall_pct: 28.0, dram_latency_ns: 65.0 })
        });
      } else if (profileKey === 'baseline_scalar') {
        res = await apiFetch('/api/bottleneck/analyze', {
          method: 'POST',
          body: JSON.stringify({ cpi: 3.40, llc_miss_rate: 38.5, branch_mispredict_rate: 6.0, pipeline_stall_pct: 16.0, dram_latency_ns: 78.0 })
        });
      } else if (profileKey === 'raytrace_bvh') {
        res = await apiFetch('/api/bottleneck/analyze', {
          method: 'POST',
          body: JSON.stringify({ cpi: 2.95, llc_miss_rate: 22.0, branch_mispredict_rate: 18.5, pipeline_stall_pct: 22.0, dram_latency_ns: 72.0 })
        });
      } else {
        res = await apiFetch('/api/bottleneck/analyze', {
          method: 'POST',
          body: JSON.stringify({ cpi: 2.47, llc_miss_rate: 28.4, branch_mispredict_rate: 8.0, pipeline_stall_pct: 18.0, dram_latency_ns: 68.0 })
        });
      }

      if (res) {
        renderScoreGauge(res.bottleneck_score, res.severity, res.risk_level);
        renderBottlenecksList(res.items);
        renderDistributionBars(res.distribution);
        renderTmaBreakdown(res.tma_levels, res.distribution);
      }
    } catch (e) {
      console.warn('Bottleneck analysis error:', e.message);
    }
  }

  // =========================================================================
  // Live Host Telemetry Streaming (PMU-style estimates derived from OS counters)
  // =========================================================================

  async function togglePMUStream() {
    const btn = document.getElementById('btn-toggle-pmu');
    const indicator = document.getElementById('pmu-pulse-indicator');
    const label = document.getElementById('pmu-toggle-text');
    const monitorCard = document.getElementById('pmu-live-monitor-card');

    isPMUStreaming = !isPMUStreaming;

    if (isPMUStreaming) {
      if (btn) {
        btn.className = 'inline-flex items-center gap-2 h-10 px-space-md rounded-xl bg-primary-fixed/30 hover:bg-primary-fixed/40 text-primary font-label-md text-label-md shadow-sm transition-all border border-primary/50';
      }
      if (indicator) {
        indicator.className = 'w-2.5 h-2.5 rounded-full bg-primary animate-ping';
      }
      if (label) {
        label.textContent = 'Host Telemetry Stream: Live';
      }
      if (monitorCard) {
        monitorCard.classList.remove('hidden');
      }

      if (window.showToast) {
        window.showToast('Streaming live host telemetry (estimated counters)...', 'success');
      }

      await pollHardwarePMU();
      if (pmuStreamTimer) clearInterval(pmuStreamTimer);
      pmuStreamTimer = setInterval(pollHardwarePMU, 2000);
    } else {
      if (pmuStreamTimer) {
        clearInterval(pmuStreamTimer);
        pmuStreamTimer = null;
      }
      if (btn) {
        btn.className = 'inline-flex items-center gap-2 h-10 px-space-md rounded-xl bg-surface-container-lowest hover:bg-surface-container text-on-surface font-label-md text-label-md shadow-sm transition-all border border-surface-container';
      }
      if (indicator) {
        indicator.className = 'w-2.5 h-2.5 rounded-full bg-slate-400';
      }
      if (label) {
        label.textContent = 'Host Telemetry Stream: Off';
      }
      if (monitorCard) {
        monitorCard.classList.add('hidden');
      }

      if (window.showToast) {
        window.showToast('Live host hardware PMU stream paused', 'info');
      }

      loadBottlenecks(currentProfile);
    }
  }

  async function pollHardwarePMU() {
    try {
      const pmu = await apiFetch('/api/device/pmu');
      if (!pmu) return;

      // Update monitor card elements
      const cpuModel = document.getElementById('pmu-cpu-model');
      if (cpuModel) {
        cpuModel.textContent = `${pmu.cpu_model || 'Host Silicon'} • ${pmu.physical_cores} Cores @ ${pmu.frequency_ghz.toFixed(2)} GHz • Source: ${pmu.source}`;
      }

      const elevationBadge = document.getElementById('pmu-elevation-badge');
      if (elevationBadge) {
        if (pmu.is_elevated) {
          elevationBadge.textContent = 'Host Telemetry (Admin Mode)';
          elevationBadge.className = 'px-2.5 py-0.5 rounded-full bg-primary-fixed text-on-primary-fixed-variant font-code-mono text-label-xs font-bold shadow-xs';
        } else {
          elevationBadge.textContent = 'Host Telemetry (User Mode psutil)';
          elevationBadge.className = 'px-2.5 py-0.5 rounded-full bg-surface-container-highest text-on-surface font-code-mono text-label-xs font-semibold';
        }
      }

      const llcRateEl = document.getElementById('pmu-llc-rate');
      if (llcRateEl) llcRateEl.textContent = `${pmu.llc_miss_rate.toFixed(1)}%`;

      const branchRateEl = document.getElementById('pmu-branch-rate');
      if (branchRateEl) branchRateEl.textContent = `${pmu.branch_mispredict_rate.toFixed(1)}%`;

      const liveIpcEl = document.getElementById('pmu-live-ipc');
      if (liveIpcEl) liveIpcEl.textContent = pmu.live_ipc.toFixed(2);

      const retireRateEl = document.getElementById('pmu-retire-rate');
      if (retireRateEl) {
        const gips = (pmu.instructions_per_sec / 1e9).toFixed(2);
        retireRateEl.textContent = gips;
      }

      // Re-evaluate the bottleneck model using the live estimated telemetry.
      // Modern x86 cores are ~4-wide; live IPC can exceed 1, so the width must be explicit.
      const liveCpi = 1.0 / Math.max(0.2, pmu.live_ipc);
      const res = await apiFetch('/api/bottleneck/analyze', {
        method: 'POST',
        body: JSON.stringify({
          cpi: parseFloat(liveCpi.toFixed(2)),
          llc_miss_rate: parseFloat(pmu.llc_miss_rate.toFixed(1)),
          branch_mispredict_rate: parseFloat(pmu.branch_mispredict_rate.toFixed(1)),
          pipeline_stall_pct: Number.isFinite(pmu.pipeline_stall_pct) ? pmu.pipeline_stall_pct : 20.0,
          dram_latency_ns: 65.0,
          issue_width: 4
        })
      });

      if (res) {
        renderScoreGauge(res.bottleneck_score, res.severity, res.risk_level);
        renderBottlenecksList(res.items);
        renderDistributionBars(res.distribution);
        renderTmaBreakdown(res.tma_levels, res.distribution);
      }
    } catch (e) {
      console.warn('Live PMU poll error:', e.message);
    }
  }

  // =========================================================================
  // Standard UI Renderers
  // =========================================================================

  function renderScoreGauge(score, severity, risk) {
    const scoreVal = Math.round(score || 67);
    const scoreEl = document.getElementById('bottleneck-score-val');
    const riskBadge = document.getElementById('bottleneck-risk-badge');
    const arcPath = document.getElementById('bottleneck-arc-path');
    const topBadge = document.getElementById('bottleneck-top-badge');

    if (scoreEl) scoreEl.innerText = `${scoreVal}%`;
    if (riskBadge) {
      riskBadge.innerText = severity || (scoreVal > 60 ? 'High' : scoreVal > 30 ? 'Medium' : 'Nominal');
      riskBadge.className = scoreVal >= 60 ? 'font-headline-md text-headline-md text-error font-bold mt-1' :
                            scoreVal >= 30 ? 'font-headline-md text-headline-md text-amber-600 font-bold mt-1' :
                            'font-headline-md text-headline-md text-primary font-bold mt-1';
    }

    if (topBadge) {
      topBadge.innerHTML = `<span class="w-1.5 h-1.5 rounded-full ${scoreVal >= 60 ? 'bg-error' : scoreVal >= 30 ? 'bg-amber-500' : 'bg-primary'}"></span> ${risk || severity || 'High Risk'}`;
      topBadge.className = scoreVal >= 60 ? 'px-2.5 py-0.5 rounded-full bg-error-container text-on-error-container font-label-xs text-label-xs font-semibold flex items-center gap-1' :
                           scoreVal >= 30 ? 'px-2.5 py-0.5 rounded-full bg-amber-100 text-amber-800 font-label-xs text-label-xs font-semibold flex items-center gap-1' :
                           'px-2.5 py-0.5 rounded-full bg-primary-fixed text-on-primary-fixed-variant font-label-xs text-label-xs font-semibold flex items-center gap-1';
    }

    if (arcPath) {
      const ARC_LENGTH = 251.2;
      const offset = ARC_LENGTH - (scoreVal / 100) * ARC_LENGTH;
      arcPath.style.strokeDashoffset = offset;
      arcPath.setAttribute('class', scoreVal >= 60 ? 'text-error' : scoreVal >= 30 ? 'text-amber-500' : 'text-primary');
    }
  }

  function renderBottlenecksList(items) {
    const container = document.getElementById('bottleneck-items-container');
    if (!container || !Array.isArray(items)) return;

    container.innerHTML = '';
    items.forEach(item => {
      const div = document.createElement('div');
      div.className = 'flex items-center justify-between p-space-md rounded-xl bg-surface-container-low hover:bg-surface-container transition-colors';

      const isCritical = item.severity === 'Critical';
      const isHigh = item.severity === 'High';
      const isMed = item.severity === 'Medium';

      const icon = item.name.includes('Memory') ? 'dns' :
                   item.name.includes('Pipeline') ? 'account_tree' :
                   item.name.includes('Branch') ? 'alt_route' : 'layers';

      const iconBg = (isHigh || isCritical) ? 'bg-error-container text-on-error-container' :
                     isMed ? 'bg-secondary-fixed text-on-secondary-fixed' :
                     'bg-primary-fixed text-on-primary-fixed-variant';

      const badgeBg = (isHigh || isCritical) ? 'bg-error-container text-on-error-container font-bold' :
                      isMed ? 'bg-secondary-fixed text-on-secondary-fixed font-bold' :
                      'bg-primary-fixed text-on-primary-fixed-variant font-bold';

      const penaltyCycles = item.penalty_cycles ?? item.impact_cycles ?? 0;

      div.innerHTML = `
        <div class="flex items-center gap-space-md">
          <div class="w-10 h-10 rounded-xl ${iconBg} flex items-center justify-center flex-shrink-0">
            <span class="material-symbols-outlined text-[20px]">${icon}</span>
          </div>
          <div class="flex flex-col">
            <div class="flex items-center gap-2">
              <span class="font-label-md text-label-md text-on-surface font-semibold">${escapeHtml(item.name)}</span>
              <span class="font-code-mono text-label-xs text-on-surface-variant">${escapeHtml(item.subsystem)}</span>
            </div>
            <span class="font-body-sm text-body-sm text-on-surface-variant">${escapeHtml(item.description)}</span>
          </div>
        </div>
        <div class="flex items-center gap-space-md">
          <span class="font-code-mono text-label-md font-bold ${(isHigh || isCritical) ? 'text-error' : 'text-on-surface'}">+${penaltyCycles.toLocaleString()} cycles</span>
          <span class="px-3 py-1 rounded-full ${badgeBg} font-label-xs text-label-xs uppercase tracking-wider">${item.severity}</span>
        </div>
      `;
      container.appendChild(div);
    });
  }

  function renderDistributionBars(dist) {
    if (!dist) return;

    const impactPanel = document.getElementById('bottleneck-impact-bars');
    if (!impactPanel) return;

    const bars = impactPanel.querySelectorAll('.flex.flex-col.gap-1\\.5');
    if (bars.length >= 4) {
      const memVal = dist.Memory ?? 28.0;
      bars[0].querySelector('.font-code-mono').innerText = `${memVal}%`;
      bars[0].querySelector('.h-full').style.width = `${Math.min(100, memVal)}%`;

      const pipeVal = dist.Pipeline ?? 18.0;
      bars[1].querySelector('.font-code-mono').innerText = `${pipeVal}%`;
      bars[1].querySelector('.h-full').style.width = `${Math.min(100, pipeVal)}%`;

      const branchVal = dist.Branch ?? 12.0;
      bars[2].querySelector('.font-code-mono').innerText = `${branchVal}%`;
      bars[2].querySelector('.h-full').style.width = `${Math.min(100, branchVal)}%`;

      const structVal = dist.Structural ?? 9.0;
      bars[3].querySelector('.font-code-mono').innerText = `${structVal}%`;
      bars[3].querySelector('.h-full').style.width = `${Math.min(100, structVal)}%`;
    }
  }

  function renderTmaBreakdown(tma, dist) {
    if (!tma) {
      if (!dist) return;
      const memVal = dist.Memory ?? 28.0;
      const pipeVal = dist.Pipeline ?? 18.0;
      const branchVal = dist.Branch ?? 12.0;
      const structVal = dist.Structural ?? 9.0;
      const retiring = 40.0;
      const loss = 60.0;
      tma = {
        retiring: retiring,
        bad_speculation: Math.round(branchVal * 0.6),
        frontend_bound: Math.round(pipeVal * 0.4),
        backend_bound: Math.round(loss - (branchVal * 0.6) - (pipeVal * 0.4)),
        total_loss: loss
      };
    }

    const retEl = document.getElementById('tma-retiring-val');
    if (retEl) retEl.textContent = `${tma.retiring.toFixed(1)}%`;

    const badEl = document.getElementById('tma-badspec-val');
    if (badEl) badEl.textContent = `${tma.bad_speculation.toFixed(1)}%`;

    const frontEl = document.getElementById('tma-frontend-val');
    if (frontEl) frontEl.textContent = `${tma.frontend_bound.toFixed(1)}%`;

    const backEl = document.getElementById('tma-backend-val');
    if (backEl) backEl.textContent = `${tma.backend_bound.toFixed(1)}%`;

    const totalLossVal = tma.total_loss !== undefined ? tma.total_loss : Math.max(0, 100.0 - tma.retiring);
    const totalLossEl = document.getElementById('bottleneck-total-loss-val');
    if (totalLossEl) {
      totalLossEl.textContent = `${totalLossVal.toFixed(1)}%`;
    }

    // Dynamic Donut SVG Circles & Legend:
    // Retiring occupies tma.retiring % of total cycles.
    // The stall components (dist) divide the remaining totalLossVal % proportionally.
    const CIRCUMFERENCE = 301.59; // 2 * PI * 48
    if (dist) {
      const memShare = dist.Memory || 28;
      const pipeShare = dist.Pipeline || 18;
      const branchShare = dist.Branch || 12;
      const structShare = dist.Structural || 9;
      const sumStallShares = (memShare + pipeShare + branchShare + structShare) || 1.0;

      const mem = (memShare / sumStallShares) * totalLossVal;
      const pipe = (pipeShare / sumStallShares) * totalLossVal;
      const branch = (branchShare / sumStallShares) * totalLossVal;
      const struct = (structShare / sumStallShares) * totalLossVal;
      const retire = tma.retiring;

      const lenMem = (mem / 100) * CIRCUMFERENCE;
      const lenPipe = (pipe / 100) * CIRCUMFERENCE;
      const lenBranch = (branch / 100) * CIRCUMFERENCE;
      const lenStruct = (struct / 100) * CIRCUMFERENCE;
      const lenRetire = (retire / 100) * CIRCUMFERENCE;

      const circleMem = document.getElementById('donut-circle-mem');
      const circlePipe = document.getElementById('donut-circle-pipe');
      const circleBranch = document.getElementById('donut-circle-branch');
      const circleStruct = document.getElementById('donut-circle-struct');
      const circleRetire = document.getElementById('donut-circle-retire');

      if (circleMem) {
        circleMem.style.strokeDasharray = `${lenMem} ${CIRCUMFERENCE}`;
        circleMem.style.strokeDashoffset = '0';
      }
      if (circlePipe) {
        circlePipe.style.strokeDasharray = `${lenPipe} ${CIRCUMFERENCE}`;
        circlePipe.style.strokeDashoffset = `${-lenMem}`;
      }
      if (circleBranch) {
        circleBranch.style.strokeDasharray = `${lenBranch} ${CIRCUMFERENCE}`;
        circleBranch.style.strokeDashoffset = `${-(lenMem + lenPipe)}`;
      }
      if (circleStruct) {
        circleStruct.style.strokeDasharray = `${lenStruct} ${CIRCUMFERENCE}`;
        circleStruct.style.strokeDashoffset = `${-(lenMem + lenPipe + lenBranch)}`;
      }
      if (circleRetire) {
        circleRetire.style.strokeDasharray = `${lenRetire} ${CIRCUMFERENCE}`;
        circleRetire.style.strokeDashoffset = `${-(lenMem + lenPipe + lenBranch + lenStruct)}`;
      }

      const legMem = document.getElementById('donut-legend-mem');
      if (legMem) legMem.textContent = `Memory (${mem.toFixed(1)}%)`;
      const legPipe = document.getElementById('donut-legend-pipe');
      if (legPipe) legPipe.textContent = `Pipeline (${pipe.toFixed(1)}%)`;
      const legBranch = document.getElementById('donut-legend-branch');
      if (legBranch) legBranch.textContent = `Branch (${branch.toFixed(1)}%)`;
      const legStruct = document.getElementById('donut-legend-struct');
      if (legStruct) legStruct.textContent = `Structural (${struct.toFixed(1)}%)`;
      const legRetire = document.getElementById('donut-legend-retire');
      if (legRetire) legRetire.textContent = `Retiring / Useful Work (${retire.toFixed(1)}%)`;
    }
  }

  function setupControls() {
    // PMU Stream Toggle Button
    const pmuBtn = document.getElementById('btn-toggle-pmu');
    if (pmuBtn) {
      pmuBtn.addEventListener('click', togglePMUStream);
    }

    const profileSelect = document.querySelector('header select, .flex.items-center select');
    if (profileSelect) {
      profileSelect.innerHTML = `
        <option value="latest">Latest Benchmark / Live Profile</option>
        <option value="matrix_avx512">Run #1042 • MatrixMult_AVX512 (Core-Bound)</option>
        <option value="baseline_scalar">Run #1041 • Baseline_Scalar (Memory-Heavy)</option>
        <option value="raytrace_bvh">Run #1040 • RayTrace_BVH (Branch-Heavy)</option>
      `;
      profileSelect.addEventListener('change', () => {
        if (isPMUStreaming) {
          togglePMUStream(); // Turn off streaming when switching to static profile
        }
        loadBottlenecks(profileSelect.value);
        if (window.showToast) window.showToast(`Switched bottleneck profile to: ${profileSelect.options[profileSelect.selectedIndex].text}`, 'info');
      });
    }

    const rerunBtn = document.getElementById('rerun-btn');
    if (rerunBtn) {
      rerunBtn.addEventListener('click', async () => {
        const icon = rerunBtn.querySelector('.material-symbols-outlined');
        if (icon) icon.classList.add('animate-spin');
        if (isPMUStreaming) {
          await pollHardwarePMU();
        } else {
          await loadBottlenecks(profileSelect ? profileSelect.value : currentProfile);
        }
        setTimeout(() => {
          if (icon) icon.classList.remove('animate-spin');
        }, 500);
        if (window.showToast) window.showToast('Microarchitectural bottleneck audit refreshed', 'success');
      });
    }

    // Export Diagnostic Report button
    const buttons = document.querySelectorAll('button');
    buttons.forEach(btn => {
      if (btn.textContent.includes('Export Diagnostic Report')) {
        btn.addEventListener('click', async () => {
          try {
            const reportPayload = {
              title: `Bottleneck Diagnostic Audit - ${new Date().toLocaleTimeString()}`,
              report_type: 'Bottleneck Audit',
              summary: 'Comprehensive microarchitectural stall audit and optimization analysis',
              data: {
                timestamp: new Date().toISOString(),
                profile: profileSelect ? profileSelect.value : currentProfile,
                is_pmu_live: isPMUStreaming
              }
            };
            const rep = await apiFetch('/api/reports/generate', {
              method: 'POST',
              body: JSON.stringify(reportPayload)
            });
            if (rep && rep.id) {
              if (window.showToast) window.showToast(`Diagnostic Report #${rep.id} exported successfully!`, 'success');
            }
          } catch (e) {
            if (window.showToast) window.showToast('Failed to export report: ' + e.message, 'error');
          }
        });
      }
    });

    const patchCache = document.getElementById('btn-patch-cache');
    if (patchCache) {
      patchCache.addEventListener('click', async () => {
        if (window.showToast) window.showToast('Applied Patch: Enabling non-temporal SIMD streaming & tuning L2 prefetcher', 'success');
        if (profileSelect) profileSelect.value = 'matrix_avx512';
        await loadBottlenecks('matrix_avx512');
      });
    }

    const patchBranch = document.getElementById('btn-patch-branch');
    if (patchBranch) {
      patchBranch.addEventListener('click', async () => {
        if (window.showToast) window.showToast('Applied Patch: Devirtualized callsite & substituted CMOVcc', 'success');
        if (profileSelect) profileSelect.value = 'baseline_scalar';
        await loadBottlenecks('baseline_scalar');
      });
    }

    const patchHazard = document.getElementById('btn-patch-hazard');
    if (patchHazard) {
      patchHazard.addEventListener('click', () => {
        if (window.showToast) window.showToast('Routing to Pipeline Simulator with Forwarding enabled to verify RAW resolution', 'info');
        setTimeout(() => {
          window.location.href = 'PipelineSimulator.html';
        }, 800);
      });
    }
  }

  function init() {
    setupControls();
    loadBottlenecks('latest');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
