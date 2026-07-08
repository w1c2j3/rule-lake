// Rule Lake 前端交互脚本。
// 主要负责：移动导航、实验表单联动、表格搜索/排序/导出、
// 实验历史、规则收藏、报告复制、数据预览和算法教学可视化。
// 说明：命名函数/工具函数均有独立注释；短小匿名回调紧贴 DOM 事件，
// 其作用由所在功能块注释和内部变量名共同限定，便于阅读时顺着页面模块定位。
document.addEventListener("DOMContentLoaded", () => {
    // 移动端侧边栏开关。
    const navToggle = document.querySelector("[data-nav-toggle]");
    const navLinks = document.querySelector("[data-nav-links]");

    if (navToggle && navLinks) {
        navToggle.addEventListener("click", () => {
            navLinks.classList.toggle("open");
        });
    }

    // 同步 range 滑块和右侧任务状态面板中的参数值。
    const syncSlider = (slider) => {
        const output = document.querySelector(`[data-slider-output="${slider.name}"]`);
        const value = Number(slider.value).toFixed(2);
        if (output) {
            output.textContent = value;
        }
        if (slider.name === "min_support") {
            document.querySelectorAll("[data-active-support]").forEach((node) => {
                node.textContent = value;
            });
        }
        if (slider.name === "min_confidence") {
            document.querySelectorAll("[data-active-confidence]").forEach((node) => {
                node.textContent = value;
            });
        }
    };

    document.querySelectorAll('input[type="range"]').forEach((slider) => {
        slider.addEventListener("input", () => syncSlider(slider));
        syncSlider(slider);
    });

    // 根据数据源模式显示对应输入区：内置数据湖、上传 CSV、本机路径。
    const datasetRadios = document.querySelectorAll('input[name="dataset_mode"]');
    const datasetSections = document.querySelectorAll("[data-dataset-section]");

    const syncDatasetFields = () => {
        const selected = document.querySelector('input[name="dataset_mode"]:checked')?.value || "builtin";
        datasetSections.forEach((section) => {
            section.hidden = section.dataset.datasetSection !== selected;
        });
    };

    datasetRadios.forEach((radio) => {
        radio.addEventListener("change", syncDatasetFields);
    });
    syncDatasetFields();

    // 算法卡片与隐藏 select 保持同步，提交表单时后端读取 select 值。
    const algorithmSelect = document.querySelector("[data-algorithm-select]");
    const algoCards = document.querySelectorAll("[data-algo-card]");
    const activeAlgo = document.querySelector("[data-active-algo]");

    algoCards.forEach((card) => {
        card.addEventListener("click", () => {
            const key = card.dataset.algoCard;
            algoCards.forEach((item) => item.classList.remove("active"));
            card.classList.add("active");
            if (algorithmSelect) {
                algorithmSelect.value = key;
            }
            if (activeAlgo) {
                activeAlgo.textContent = card.dataset.algoName || key;
            }
        });
    });

    // 参数预设按钮：探索、平衡、严格三种模式。
    document.querySelectorAll("[data-preset-support]").forEach((button) => {
        button.addEventListener("click", () => {
            document.querySelectorAll("[data-preset-support]").forEach((item) => {
                item.classList.remove("active");
            });
            button.classList.add("active");

            const support = document.querySelector('input[name="min_support"]');
            const confidence = document.querySelector('input[name="min_confidence"]');
            if (support) {
                support.value = button.dataset.presetSupport;
                syncSlider(support);
            }
            if (confidence) {
                confidence.value = button.dataset.presetConfidence;
                syncSlider(confidence);
            }
        });
    });

    // 切换内置数据湖资产时，自动应用该资产推荐的支持度和置信度。
    const builtinDatasetSelect = document.querySelector("[data-builtin-dataset-select]");
    if (builtinDatasetSelect) {
        const syncBuiltinDataset = () => {
            const selected = builtinDatasetSelect.selectedOptions[0];
            if (!selected) {
                return;
            }
            const support = document.querySelector('input[name="min_support"]');
            const confidence = document.querySelector('input[name="min_confidence"]');
            const activeDataset = document.querySelector("[data-active-dataset]");
            if (activeDataset) {
                activeDataset.textContent = selected.textContent.split("-")[0].trim();
            }
            if (support && selected.dataset.support) {
                support.value = selected.dataset.support;
                syncSlider(support);
            }
            if (confidence && selected.dataset.confidence) {
                confidence.value = selected.dataset.confidence;
                syncSlider(confidence);
            }
            document.querySelectorAll("[data-preset-support]").forEach((item) => {
                item.classList.remove("active");
            });
        };
        builtinDatasetSelect.addEventListener("change", syncBuiltinDataset);
        syncBuiltinDataset();
    }

    // 数据湖预览表默认只显示部分行，展开按钮用于查看更多交易。
    document.querySelectorAll("[data-expand-table]").forEach((button) => {
        const preview = document.querySelector("[data-preview-table]");
        if (!preview) {
            return;
        }

        button.addEventListener("click", () => {
            preview.classList.toggle("table-expanded");
            const expanded = preview.classList.contains("table-expanded");
            button.textContent = expanded ? "收起预览" : "展开更多";
        });
    });

    // 推荐模拟器商品勾选：同步卡片状态、已选数量、右侧购物篮预览和候选搜索。
    const itemChips = Array.from(document.querySelectorAll("[data-item-chip]"));
    const selectedItemCount = document.querySelector("[data-selected-item-count]");
    const selectedItemList = document.querySelector("[data-selected-item-list]");
    const itemSearch = document.querySelector("[data-item-search]");
    const clearItemSelection = document.querySelector("[data-clear-item-selection]");

    const renderSelectedItems = () => {
        if (!selectedItemList) {
            return;
        }

        const selected = itemChips
            .filter((chip) => chip.querySelector('input[type="checkbox"]')?.checked)
            .map((chip) => ({
                value: chip.querySelector('input[type="checkbox"]').value,
                label: chip.querySelector(".item-chip-name")?.textContent.trim() || chip.textContent.trim(),
            }));

        selectedItemList.replaceChildren();
        if (!selected.length) {
            const empty = document.createElement("p");
            empty.textContent = selectedItemList.dataset.emptyText || "当前未选择商品。";
            selectedItemList.appendChild(empty);
        } else {
            selected.forEach((item) => {
                const badge = document.createElement("span");
                badge.dataset.selectedItem = item.value;
                badge.textContent = item.label;
                selectedItemList.appendChild(badge);
            });
        }

        if (selectedItemCount) {
            selectedItemCount.textContent = String(selected.length);
        }
    };

    const syncItemChip = (chip) => {
        const checkbox = chip.querySelector('input[type="checkbox"]');
        if (!checkbox) {
            return;
        }
        chip.classList.toggle("active", checkbox.checked);
    };

    itemChips.forEach((chip) => {
        const checkbox = chip.querySelector('input[type="checkbox"]');
        if (!checkbox) {
            return;
        }
        checkbox.addEventListener("change", () => {
            syncItemChip(chip);
            renderSelectedItems();
        });
        syncItemChip(chip);
    });
    renderSelectedItems();

    if (itemSearch) {
        itemSearch.addEventListener("input", () => {
            const keyword = itemSearch.value.trim().toLowerCase();
            itemChips.forEach((chip) => {
                chip.hidden = Boolean(keyword) && !(chip.dataset.itemSearchText || "").includes(keyword);
            });
        });
    }

    if (clearItemSelection) {
        clearItemSelection.addEventListener("click", () => {
            itemChips.forEach((chip) => {
                const checkbox = chip.querySelector('input[type="checkbox"]');
                if (checkbox) {
                    checkbox.checked = false;
                    syncItemChip(chip);
                }
            });
            renderSelectedItems();
        });
    }

    // 通用表格过滤器：支持搜索文本、规则页 lift/confidence 阈值过滤。
    const filterTable = (tableId) => {
        const table = document.getElementById(tableId);
        if (!table) {
            return;
        }

        const search = document.querySelector(`[data-table-search="${tableId}"]`)?.value.trim().toLowerCase() || "";
        const minLift = Number(document.querySelector("[data-min-lift]")?.value || 0);
        const minConfidence = Number(document.querySelector("[data-min-confidence]")?.value || 0);

        table.querySelectorAll("tbody tr").forEach((row) => {
            const textMatch = row.textContent.toLowerCase().includes(search);
            const lift = Number(row.dataset.lift || 0);
            const confidence = Number(row.dataset.confidence || 0);
            const liftMatch = tableId !== "rules-table" || lift >= minLift;
            const confidenceMatch = tableId !== "rules-table" || confidence >= minConfidence;
            row.hidden = !(textMatch && liftMatch && confidenceMatch);
        });
    };

    document.querySelectorAll("[data-table-search]").forEach((input) => {
        input.addEventListener("input", () => filterTable(input.dataset.tableSearch));
    });

    document.querySelectorAll("[data-min-lift], [data-min-confidence]").forEach((input) => {
        input.addEventListener("input", () => filterTable("rules-table"));
    });

    // 表头点击排序，数值列读取 data-value，文本列按文本排序。
    document.querySelectorAll("th[data-sortable]").forEach((header) => {
        header.addEventListener("click", () => {
            const table = header.closest("table");
            const tbody = table?.querySelector("tbody");
            if (!table || !tbody) {
                return;
            }

            const columnIndex = Array.from(header.parentNode.children).indexOf(header);
            const numeric = header.dataset.type === "number";
            const nextDir = header.dataset.dir === "asc" ? "desc" : "asc";
            header.parentNode.querySelectorAll("th").forEach((th) => delete th.dataset.dir);
            header.dataset.dir = nextDir;

            const rows = Array.from(tbody.querySelectorAll("tr"));
            rows.sort((left, right) => {
                const leftCell = left.children[columnIndex];
                const rightCell = right.children[columnIndex];
                const leftValue = numeric ? Number(leftCell?.dataset.value || leftCell?.textContent.replace("%", "") || 0) : leftCell?.textContent.trim() || "";
                const rightValue = numeric ? Number(rightCell?.dataset.value || rightCell?.textContent.replace("%", "") || 0) : rightCell?.textContent.trim() || "";
                if (leftValue < rightValue) {
                    return nextDir === "asc" ? -1 : 1;
                }
                if (leftValue > rightValue) {
                    return nextDir === "asc" ? 1 : -1;
                }
                return 0;
            });

            rows.forEach((row) => tbody.appendChild(row));
        });
    });

    // CSV 导出时需要转义引号，并保留 UTF-8 BOM 方便 Excel 打开中文。
    const csvEscape = (value) => {
        const normalized = value.replace(/\s+/g, " ").trim();
        return `"${normalized.replace(/"/g, '""')}"`;
    };

    // HTML 转义工具：所有由 localStorage 或表格文本拼出的 HTML 片段都先转义，
    // 避免用户导入的商品名中包含尖括号时破坏页面结构。
    const escapeHtml = (value) => String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");

    // 前端预览接口返回的是纯 JSON，这里复用后端注入的商品词典并做兜底生成。
    const itemTranslations = window.ruleLakeItemTranslations || {};
    const itemTokenTranslations = {
        red: "红色",
        green: "绿色",
        blue: "蓝色",
        pink: "粉色",
        white: "白色",
        black: "黑色",
        ivory: "象牙色",
        vintage: "复古",
        retrospot: "复古圆点",
        woodland: "森林图案",
        spaceboy: "太空男孩",
        dolly: "娃娃",
        girl: "女孩",
        bag: "袋",
        bags: "袋",
        jumbo: "大号",
        lunch: "午餐",
        box: "盒",
        boxes: "盒",
        case: "盒",
        cases: "盒",
        set: "套装",
        pack: "包装",
        paper: "纸",
        napkins: "餐巾纸",
        cups: "杯",
        plates: "盘",
        cake: "蛋糕",
        cakes: "蛋糕",
        tea: "茶",
        coffee: "咖啡",
        mug: "马克杯",
        ceramic: "陶瓷",
        tin: "铁盒",
        tins: "铁盒",
        heart: "爱心",
        hearts: "爱心",
        hot: "热",
        water: "水",
        bottle: "瓶",
        holder: "架",
        light: "灯",
        night: "夜灯",
        card: "卡片",
        cards: "卡片",
        christmas: "圣诞",
        kitchen: "厨房",
        pantry: "厨房",
        apple: "苹果",
        apples: "苹果",
        strawberry: "草莓",
        fruit: "水果",
        vegetable: "蔬菜",
        vegetables: "蔬菜",
        milk: "牛奶",
        cheese: "奶酪",
        bread: "面包",
        meat: "肉类",
        beef: "牛肉",
        chicken: "鸡肉",
        fish: "鱼",
        frozen: "冷冻",
        cream: "奶油",
        chocolate: "巧克力",
        sauce: "酱",
        sauces: "酱料",
        juice: "果汁",
        wine: "葡萄酒",
        beer: "啤酒",
        canned: "罐装",
        fresh: "新鲜",
        whole: "全",
        wheat: "小麦",
        rice: "米",
        pasta: "意大利面",
        snack: "零食",
        snacks: "零食",
        cookies: "曲奇",
        muffin: "松饼",
        muffins: "松饼",
    };

    const itemCnLabel = (name) => {
        const text = String(name || "").trim();
        if (!text) {
            return "";
        }
        if (itemTranslations[text]) {
            return itemTranslations[text];
        }
        const generated = Array.from(new Set(
            (text.match(/[A-Za-z0-9]+/g) || [])
                .map((token) => itemTokenTranslations[token.toLowerCase()])
                .filter(Boolean),
        ));
        return generated.length ? generated.join("") : "商品中文注释待补充";
    };

    const itemLabelHtml = (name) => {
        const text = String(name || "").trim();
        const cn = itemCnLabel(text);
        return `
            <span class="translated-item compact" title="${cn ? `${escapeHtml(cn)} / ` : ""}${escapeHtml(text)}">
                <span class="item-en">${escapeHtml(text)}</span>
                ${cn ? `<span class="item-cn">${escapeHtml(cn)}</span>` : ""}
            </span>
        `;
    };

    const itemListHtml = (text) => String(text || "")
        .split(/[、,]/)
        .map((item) => item.trim())
        .filter(Boolean)
        .map(itemLabelHtml)
        .join("");

    const translateItemText = (text) => {
        let output = String(text || "");
        Object.entries(itemTranslations)
            .sort((left, right) => right[0].length - left[0].length)
            .forEach(([en, cn]) => {
                output = output.replaceAll(en, `${en}（${cn}）`);
            });
        return output;
    };

    document.querySelectorAll("[data-translate-item-text]").forEach((node) => {
        node.textContent = translateItemText(node.textContent);
    });

    document.querySelectorAll("[data-export-table]").forEach((button) => {
        button.addEventListener("click", () => {
            const table = document.getElementById(button.dataset.exportTable);
            if (!table) {
                return;
            }

            const rows = Array.from(table.querySelectorAll("tr"))
                .filter((row) => !row.hidden)
                .map((row) => Array.from(row.children)
                    .filter((cell) => !cell.classList.contains("favorite-cell"))
                    .map((cell) => csvEscape(cell.textContent))
                    .join(","));
            const blob = new Blob([`\ufeff${rows.join("\n")}`], { type: "text/csv;charset=utf-8;" });
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = button.dataset.exportName || "rules.csv";
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);
        });
    });

    // 实验历史保存在浏览器 localStorage，适合小组演示和本机复现。
    const historyKey = "associationRuleExperimentHistory";

    // 从 localStorage 读取实验历史；解析失败时返回空数组，
    // 这样损坏的浏览器缓存不会影响页面加载。
    const readHistory = () => {
        try {
            return JSON.parse(localStorage.getItem(historyKey) || "[]");
        } catch {
            return [];
        }
    };

    // 写入实验历史，并限制最多保留 40 条记录，避免长期演示后缓存无限增长。
    const writeHistory = (items) => {
        localStorage.setItem(historyKey, JSON.stringify(items.slice(0, 40)));
    };

    // 渲染首页/侧栏中的最近实验摘要，只展示前 6 条，保持入口页面简洁。
    const renderHistory = () => {
        const target = document.querySelector("[data-history-list]");
        if (!target) {
            return;
        }
        const history = readHistory();
        if (!history.length) {
            target.innerHTML = "<p>暂无历史记录，运行一次实验后会自动保存到本浏览器。</p>";
            return;
        }
        target.innerHTML = history
            .slice(0, 6)
            .map((item) => `
                <div class="history-item">
                    <span>${escapeHtml(item.time)}</span>
                    <strong>${escapeHtml(item.algorithm)} / ${escapeHtml(item.dataset)}</strong>
                    <small>${escapeHtml(item.support)} / ${escapeHtml(item.confidence)} / ${escapeHtml(item.itemsets)} 项集 / ${escapeHtml(item.rules)} 规则 / ${escapeHtml(item.elapsed)}</small>
                </div>
            `)
            .join("");
    };

    // 历史中心页面：汇总历史次数、规则数量，并生成“重新运行”表单。
    const renderHistoryCenter = () => {
        const target = document.querySelector("[data-history-center]");
        const summary = document.querySelector("[data-history-summary]");
        const count = document.querySelector("[data-history-count]");
        if (!target && !summary && !count) {
            return;
        }

        const history = readHistory();
        const algorithms = new Set(history.map((item) => item.algorithm).filter(Boolean));
        const totalItemsets = history.reduce((sum, item) => sum + Number(item.itemsets || 0), 0);
        const totalRules = history.reduce((sum, item) => sum + Number(item.rules || 0), 0);

        if (count) {
            count.textContent = `${history.length} 条记录`;
        }

        if (summary) {
            const cards = summary.querySelectorAll(".metric-card strong");
            if (cards[0]) cards[0].textContent = history.length;
            if (cards[1]) cards[1].textContent = totalItemsets;
            if (cards[2]) cards[2].textContent = totalRules;
            if (cards[3]) cards[3].textContent = algorithms.size;
        }

        if (!target) {
            return;
        }

        if (!history.length) {
            target.innerHTML = "<p>暂无历史记录。运行一次实验后，结果页会自动保存到这里。</p>";
            return;
        }

        target.innerHTML = history
            .map((item, index) => {
                const canRerun = item.algorithm_key && item.dataset_id && item.min_support && item.min_confidence;
                const rerunForm = canRerun
                    ? `
                        <form action="/run" method="post">
                            <input type="hidden" name="dataset_mode" value="builtin">
                            <input type="hidden" name="builtin_dataset" value="${escapeHtml(item.dataset_id)}">
                            <input type="hidden" name="algorithm" value="${escapeHtml(item.algorithm_key)}">
                            <input type="hidden" name="min_support" value="${escapeHtml(item.min_support)}">
                            <input type="hidden" name="min_confidence" value="${escapeHtml(item.min_confidence)}">
                            <input type="hidden" name="max_transactions" value="${escapeHtml(item.max_transactions || 300)}">
                            <input type="hidden" name="compare_algorithms" value="on">
                            <button class="btn mini primary" type="submit">重新运行</button>
                        </form>
                    `
                    : `<button class="btn mini" type="button" disabled>旧记录不可复现</button>`;
                return `
                    <article class="history-run-card">
                        <div>
                            <span>#${index + 1} ${escapeHtml(item.time)}</span>
                            <h3>${escapeHtml(item.algorithm)} / ${escapeHtml(item.dataset)}</h3>
                            <p>support ${escapeHtml(item.support)}，confidence ${escapeHtml(item.confidence)}，${escapeHtml(item.itemsets)} 项集，${escapeHtml(item.rules)} 规则，耗时 ${escapeHtml(item.elapsed)}</p>
                        </div>
                        <div class="history-run-actions">
                            ${rerunForm}
                        </div>
                    </article>
                `;
            })
            .join("");
    };

    // 从结果页隐藏 payload 中提取本次实验元数据，并追加到浏览器历史。
    // payload 由后端生成，包含算法、数据集、阈值、结果数量和耗时等字段。
    const saveCurrentResultToHistory = () => {
        const source = document.querySelector("[data-history-payload]");
        if (!source) {
            return;
        }
        try {
            const payload = JSON.parse(source.dataset.historyPayload);
            const item = {
                ...payload,
                time: new Date().toLocaleString(),
            };
            const history = readHistory();
            writeHistory([item, ...history]);
        } catch {
            return;
        }
    };

    document.querySelector("[data-save-history]")?.addEventListener("click", () => {
        saveCurrentResultToHistory();
        alert("已保存到实验历史。");
    });

    if (document.querySelector("[data-history-payload]")) {
        saveCurrentResultToHistory();
    }

    document.querySelectorAll("[data-clear-history]").forEach((button) => {
        button.addEventListener("click", () => {
            localStorage.removeItem(historyKey);
            renderHistory();
            renderHistoryCenter();
        });
    });

    renderHistory();
    renderHistoryCenter();

    document.querySelector("[data-export-history]")?.addEventListener("click", () => {
        const blob = new Blob([JSON.stringify(readHistory(), null, 2)], { type: "application/json;charset=utf-8;" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = "association_rule_history.json";
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    });

    document.querySelector("[data-copy-history]")?.addEventListener("click", async () => {
        const history = readHistory();
        const lines = history.map((item, index) => `${index + 1}. ${item.algorithm} / ${item.dataset} / support ${item.support} / confidence ${item.confidence} / ${item.itemsets} 项集 / ${item.rules} 规则 / ${item.elapsed}`);
        await copyText(lines.length ? lines.join("\n") : "暂无历史记录。");
        alert("历史摘要已复制。");
    });

    document.querySelector("[data-print-report]")?.addEventListener("click", () => {
        window.print();
    });

    // 规则收藏用于在结果页临时标记适合汇报展示的规则。
    const favoriteKey = "associationRuleFavoriteRules";

    // 读取已收藏的关联规则；异常数据直接丢弃，保证结果页可继续渲染。
    const readFavorites = () => {
        try {
            return JSON.parse(localStorage.getItem(favoriteKey) || "[]");
        } catch {
            return [];
        }
    };

    // 写入收藏规则，并限制最多 30 条，便于小组从结果页挑选汇报材料。
    const writeFavorites = (items) => {
        localStorage.setItem(favoriteKey, JSON.stringify(items.slice(0, 30)));
    };

    // 从规则表格一行中抽取收藏需要的字段。
    const getRuleFromRow = (row) => {
        const cells = Array.from(row.children).filter((cell) => !cell.classList.contains("favorite-cell"));
        const payload = document.querySelector("[data-history-payload]");
        let context = {};
        try {
            context = payload ? JSON.parse(payload.dataset.historyPayload) : {};
        } catch {
            context = {};
        }
        return {
            id: `${context.algorithm || "Algorithm"}|${context.dataset || "Dataset"}|${cells[0]?.textContent.trim()}=>${cells[1]?.textContent.trim()}`,
            algorithm: context.algorithm || "Algorithm",
            dataset: context.dataset || "Dataset",
            antecedent: cells[0]?.textContent.trim() || "",
            consequent: cells[1]?.textContent.trim() || "",
            support: cells[2]?.textContent.trim() || "",
            confidence: cells[3]?.textContent.trim() || "",
            lift: cells[4]?.textContent.trim() || "",
        };
    };

    // 渲染收藏规则面板；收藏为空时展示引导文案，有数据时展示规则和指标。
    const renderFavorites = () => {
        const panel = document.querySelector("[data-favorite-rules]");
        const favorites = readFavorites();
        if (!panel) {
            return;
        }
        if (!favorites.length) {
            panel.innerHTML = "<p>点击关联规则表格中的“+”按钮后，这里会汇总适合展示的规则。</p>";
            return;
        }
        panel.innerHTML = favorites
            .map((rule) => `
                <div>
                    <strong>${rule.antecedent} -> ${rule.consequent}</strong>
                    <small>${rule.algorithm} / ${rule.dataset} / support ${rule.support} / confidence ${rule.confidence} / lift ${rule.lift}</small>
                </div>
            `)
            .join("");
    };

    // 根据收藏状态同步规则表格中的按钮样式，避免刷新筛选后按钮状态错乱。
    const syncFavoriteButtons = () => {
        const ids = new Set(readFavorites().map((rule) => rule.id));
        document.querySelectorAll("[data-favorite-rule]").forEach((button) => {
            const row = button.closest("tr");
            if (!row) {
                return;
            }
            const rule = getRuleFromRow(row);
            const active = ids.has(rule.id);
            button.classList.toggle("active", active);
            button.textContent = active ? "OK" : "+";
        });
    };

    document.querySelectorAll("[data-favorite-rule]").forEach((button) => {
        button.addEventListener("click", () => {
            const row = button.closest("tr");
            if (!row) {
                return;
            }
            const rule = getRuleFromRow(row);
            const favorites = readFavorites();
            const exists = favorites.some((item) => item.id === rule.id);
            writeFavorites(exists ? favorites.filter((item) => item.id !== rule.id) : [rule, ...favorites]);
            syncFavoriteButtons();
            renderFavorites();
        });
    });

    document.querySelector("[data-clear-favorites]")?.addEventListener("click", () => {
        localStorage.removeItem(favoriteKey);
        syncFavoriteButtons();
        renderFavorites();
    });

    syncFavoriteButtons();
    renderFavorites();

    // 强规则快捷筛选：lift > 1 且 confidence 至少 0.5。
    document.querySelector("[data-strong-rules]")?.addEventListener("click", () => {
        const liftInput = document.querySelector("[data-min-lift]");
        const confidenceInput = document.querySelector("[data-min-confidence]");
        if (liftInput) {
            liftInput.value = "1";
        }
        if (confidenceInput && Number(confidenceInput.value || 0) < 0.5) {
            confidenceInput.value = "0.5";
        }
        filterTable("rules-table");
        document.querySelectorAll("#rules-table tbody tr").forEach((row) => {
            const lift = Number(row.dataset.lift || 0);
            const confidence = Number(row.dataset.confidence || 0);
            row.classList.toggle("strong-rule-row", lift > 1 && confidence >= 0.5 && !row.hidden);
        });
    });

    // 复制文本，优先使用 Clipboard API，旧环境回退到 textarea。
    const copyText = async (text) => {
        if (navigator.clipboard?.writeText) {
            await navigator.clipboard.writeText(text);
            return;
        }
        const textarea = document.createElement("textarea");
        textarea.value = text;
        textarea.setAttribute("readonly", "");
        textarea.style.position = "fixed";
        textarea.style.left = "-9999px";
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
    };

    // 结果页一键复制 Markdown 报告摘要。
    document.querySelector("[data-copy-report]")?.addEventListener("click", async () => {
        const payloadSource = document.querySelector("[data-history-payload]");
        let payload = {};
        try {
            payload = payloadSource ? JSON.parse(payloadSource.dataset.historyPayload) : {};
        } catch {
            payload = {};
        }
        const topRules = Array.from(document.querySelectorAll("#rules-table tbody tr"))
            .filter((row) => !row.hidden && row.dataset.lift)
            .slice(0, 8)
            .map((row, index) => {
                const cells = Array.from(row.children).filter((cell) => !cell.classList.contains("favorite-cell"));
                return `${index + 1}. ${cells[0]?.textContent.trim()} -> ${cells[1]?.textContent.trim()}，support ${cells[2]?.textContent.trim()}，confidence ${cells[3]?.textContent.trim()}，lift ${cells[4]?.textContent.trim()}`;
            });
        const report = [
            `# 关联规则挖掘实验报告`,
            ``,
            `- 算法：${payload.algorithm || ""}`,
            `- 数据湖资产：${payload.dataset || ""}`,
            `- 最小支持度：${payload.support || ""}`,
            `- 最小置信度：${payload.confidence || ""}`,
            `- 频繁项集数量：${payload.itemsets || ""}`,
            `- 关联规则数量：${payload.rules || ""}`,
            `- 运行耗时：${payload.elapsed || ""}`,
            ``,
            `## Top 规则`,
            ...(topRules.length ? topRules : ["当前筛选条件下没有可复制的规则。"]),
        ].join("\n");
        await copyText(report);
        alert("Markdown 报告已复制。");
    });

    // 数据湖注解只保存在当前浏览器，不改动服务器端数据或接口。
    const datasetNotePanel = document.querySelector("[data-dataset-note]");
    if (datasetNotePanel) {
        const datasetId = datasetNotePanel.dataset.datasetNote;
        const noteKey = `ruleLakeDatasetNote:${datasetId}`;
        const input = datasetNotePanel.querySelector("[data-dataset-note-input]");
        const status = datasetNotePanel.querySelector("[data-dataset-note-status]");
        const clearButton = datasetNotePanel.querySelector("[data-clear-dataset-note]");

        const syncNoteStatus = () => {
            const length = input?.value.trim().length || 0;
            if (status) {
                status.textContent = length ? `已保存 ${length} 个字符` : "未填写注解";
            }
        };

        if (input) {
            input.value = localStorage.getItem(noteKey) || "";
            syncNoteStatus();
            input.addEventListener("input", () => {
                localStorage.setItem(noteKey, input.value);
                syncNoteStatus();
            });
        }

        clearButton?.addEventListener("click", () => {
            localStorage.removeItem(noteKey);
            if (input) {
                input.value = "";
            }
            syncNoteStatus();
        });
    }

    // 实验页数据湖资产预览：提交当前表单给 /preview_dataset。
    document.querySelector("[data-preview-dataset]")?.addEventListener("click", async () => {
        const form = document.querySelector(".experiment-form");
        const target = document.querySelector("[data-dataset-preview]");
        if (!form || !target) {
            return;
        }
        target.hidden = false;
        target.innerHTML = "<p>正在校验数据湖资产...</p>";

        try {
            const response = await fetch("/preview_dataset", {
                method: "POST",
                body: new FormData(form),
            });
            const payload = await response.json();
            if (!payload.ok) {
                target.innerHTML = `<p>${payload.error || "数据湖资产校验失败。"}</p>`;
                return;
            }
            target.innerHTML = `
                <h3>${payload.label}</h3>
                <div class="preview-metrics">
                    <div><span>交易数</span><strong>${payload.transaction_count}</strong></div>
                    <div><span>商品数</span><strong>${payload.item_count}</strong></div>
                    <div><span>平均篮子</span><strong>${payload.avg_basket_size}</strong></div>
                    <div><span>密度</span><strong>${payload.density}%</strong></div>
                </div>
                <table class="preview-table">
                    <thead><tr><th>transaction_id</th><th>items</th></tr></thead>
                    <tbody>
                        ${payload.preview_rows
                            .map((row) => `<tr><td>${escapeHtml(row.transaction_id)}</td><td><span class="translated-item-list">${itemListHtml(row.items_text)}</span></td></tr>`)
                            .join("")}
                    </tbody>
                </table>
            `;
        } catch (error) {
            target.innerHTML = `<p>数据湖资产校验失败：${error.message}</p>`;
        }
    });

    // 表单提交后禁用按钮，避免用户连续点击触发重复实验。
    document.querySelectorAll(".experiment-form").forEach((form) => {
        form.addEventListener("submit", () => {
            const button = form.querySelector(".launch-btn");
            if (button) {
                button.textContent = "实验运行中...";
                button.disabled = true;
            }
        });
    });

    // 以下为算法教学页的可视化演示逻辑；其他页面没有 visual-canvas 时直接退出。
    const visualCanvas = document.getElementById("visual-canvas");
    if (!visualCanvas) {
        return;
    }

    const demoTransactions = [
        { id: "T1", items: ["牛奶", "面包", "黄油"] },
        { id: "T2", items: ["牛奶", "面包", "尿布", "啤酒"] },
        { id: "T3", items: ["面包", "黄油"] },
        { id: "T4", items: ["牛奶", "尿布", "啤酒"] },
        { id: "T5", items: ["面包", "牛奶", "黄油"] },
    ];

    const visualState = {
        algo: "apriori",
        step: 0,
    };

    // 三种算法的教学步骤配置：每一步包含标题、解释、公式和渲染函数。
    const visualMeta = {
        apriori: {
            title: "Apriori 可视化",
            steps: [
                {
                    code: "STEP 01",
                    title: "扫描单项支持度",
                    text: "先统计每个商品在多少条交易中出现。最小支持度计数为 2，因此出现次数小于 2 的商品会被剪枝。",
                    formula: "support(A) = count(A) / 总交易数",
                    render: renderAprioriSingles,
                },
                {
                    code: "STEP 02",
                    title: "过滤 L1 频繁 1 项集",
                    text: "保留支持度计数大于等于 2 的商品。这个 L1 会作为下一轮生成候选二项集的基础。",
                    formula: "L1 = { item | count(item) >= 2 }",
                    render: renderAprioriL1,
                },
                {
                    code: "STEP 03",
                    title: "连接生成 C2 并剪枝",
                    text: "把 L1 中的商品两两组合生成 C2，再扫描交易计算每个组合的出现次数，低支持度组合被剪掉。",
                    formula: "C2 = L1 × L1，L2 = { pair | count(pair) >= 2 }",
                    render: renderAprioriPairs,
                },
                {
                    code: "STEP 04",
                    title: "生成关联规则",
                    text: "从频繁项集中拆分前件和后件，计算 confidence 和 lift。高 confidence 表示规则稳定，lift 大于 1 表示正相关。",
                    formula: "confidence(A→B)=support(A∪B)/support(A)",
                    render: renderAprioriRules,
                },
            ],
        },
        fpgrowth: {
            title: "FP-Growth 可视化",
            steps: [
                {
                    code: "STEP 01",
                    title: "统计频率并排序",
                    text: "先统计单项频率，删除低支持度项，然后按全局频率对商品排序。排序是构建压缩树的前提。",
                    formula: "order(item) = 按 count(item) 从高到低排列",
                    render: renderFPSingles,
                },
                {
                    code: "STEP 02",
                    title: "重排每条交易",
                    text: "每条交易都按照全局频率顺序重排。这样相同前缀会靠在一起，为共享树路径做准备。",
                    formula: "transaction' = sort(transaction, global frequency)",
                    render: renderFPSortedTransactions,
                },
                {
                    code: "STEP 03",
                    title: "构建 FP-Tree",
                    text: "把排序后的交易逐条插入树。相同前缀共享节点，节点计数累加，这就是 FP-Growth 压缩数据库的关键。",
                    formula: "shared prefix path + node.count += 1",
                    render: renderFPTree,
                },
                {
                    code: "STEP 04",
                    title: "条件模式基挖掘",
                    text: "以某个后缀商品为目标，回溯它在树中的前缀路径，得到条件模式基，再递归挖掘频繁模式。",
                    formula: "conditional pattern base(item) = prefix paths ending with item",
                    render: renderFPConditional,
                },
            ],
        },
        eclat: {
            title: "Eclat 可视化",
            steps: [
                {
                    code: "STEP 01",
                    title: "转换为垂直 TID-set",
                    text: "Eclat 不反复扫描水平交易表，而是把每个商品映射到出现它的交易 ID 集合。",
                    formula: "item → { transaction ids }",
                    render: renderEclatTidsets,
                },
                {
                    code: "STEP 02",
                    title: "集合交集计算支持度",
                    text: "组合项集的 TID-set 等于各商品 TID-set 的交集，交集大小就是支持度计数。",
                    formula: "TID(A∪B)=TID(A)∩TID(B)",
                    render: renderEclatIntersection,
                },
                {
                    code: "STEP 03",
                    title: "递归扩展前缀",
                    text: "从一个频繁前缀继续和后续项做交集，交集仍满足阈值就继续扩展，否则停止。",
                    formula: "prefix + item → new TID-set",
                    render: renderEclatPrefix,
                },
                {
                    code: "STEP 04",
                    title: "输出频繁项集和规则",
                    text: "所有保留下来的前缀组合就是频繁项集，再用相同的 confidence/lift 公式生成关联规则。",
                    formula: "frequent itemsets → association rules",
                    render: renderEclatRules,
                },
            ],
        },
    };

    // 教学演示统一使用同一组迷你交易，便于横向比较三种算法思想。
    const supportCounts = countItems(demoTransactions);
    const frequentItems = Object.entries(supportCounts)
        .filter(([, count]) => count >= 2)
        .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]));
    const frequentItemNames = frequentItems.map(([item]) => item);
    const pairCounts = countPairs(demoTransactions, frequentItemNames);

    renderDemoBaskets();
    bindVisualizer();
    renderVisualizer();

    function renderDemoBaskets() {
        // 渲染左侧教学用迷你购物篮。
        const target = document.getElementById("demo-baskets");
        if (!target) {
            return;
        }
        const itemState = (item) => {
            if (["牛奶", "面包"].includes(item)) {
                return "keep";
            }
            if (item === "黄油") {
                return "candidate";
            }
            return "drop";
        };
        target.innerHTML = demoTransactions
            .map((transaction) => `
                <div class="demo-basket">
                    <strong>${transaction.id}</strong>
                    <span>${transaction.items.map((item) => `<i class="${itemState(item)}">${item}</i>`).join("")}</span>
                </div>
            `)
            .join("");
    }

    function bindVisualizer() {
        // 绑定算法切换和步骤切换按钮。
        document.querySelectorAll("[data-visual-algo]").forEach((button) => {
            button.addEventListener("click", () => {
                visualState.algo = button.dataset.visualAlgo;
                visualState.step = 0;
                document.querySelectorAll("[data-visual-algo]").forEach((item) => item.classList.remove("active"));
                button.classList.add("active");
                renderVisualizer();
            });
        });

        document.getElementById("prev-step")?.addEventListener("click", () => {
            const steps = visualMeta[visualState.algo].steps;
            visualState.step = (visualState.step - 1 + steps.length) % steps.length;
            renderVisualizer();
        });

        document.getElementById("next-step")?.addEventListener("click", () => {
            const steps = visualMeta[visualState.algo].steps;
            visualState.step = (visualState.step + 1) % steps.length;
            renderVisualizer();
        });
    }

    function renderVisualizer() {
        // 根据当前算法和步骤刷新教学画布、说明文字和步骤轨道。
        const meta = visualMeta[visualState.algo];
        const step = meta.steps[visualState.step];
        document.getElementById("visual-title").textContent = meta.title;
        document.getElementById("step-code").textContent = step.code;
        document.getElementById("step-title").textContent = step.title;
        document.getElementById("step-text").textContent = step.text;
        document.getElementById("formula-box").textContent = step.formula;
        document.getElementById("step-track").innerHTML = meta.steps
            .map((item, index) => `
                <button class="${index === visualState.step ? "active" : ""}" type="button" data-step-index="${index}">
                    <span>${String(index + 1).padStart(2, "0")}</span>
                    ${item.title}
                </button>
            `)
            .join("");
        document.querySelectorAll("[data-step-index]").forEach((button) => {
            button.addEventListener("click", () => {
                visualState.step = Number(button.dataset.stepIndex);
                renderVisualizer();
            });
        });
        step.render();
    }

    function countItems(transactions) {
        // 统计教学交易中的单项支持度计数。
        const counts = {};
        transactions.forEach((transaction) => {
            transaction.items.forEach((item) => {
                counts[item] = (counts[item] || 0) + 1;
            });
        });
        return counts;
    }

    function countPairs(transactions, items) {
        // 统计教学交易中的二项组合支持度计数。
        const pairs = {};
        for (let left = 0; left < items.length; left += 1) {
            for (let right = left + 1; right < items.length; right += 1) {
                const pair = [items[left], items[right]];
                const key = pair.join("+");
                pairs[key] = transactions.filter((transaction) => pair.every((item) => transaction.items.includes(item))).length;
            }
        }
        return pairs;
    }

    function itemCards(entries, options = {}) {
        // 生成支持度条形卡片，keep/drop 对应频繁项和被剪枝项。
        const max = Math.max(...entries.map(([, count]) => count), 1);
        return `
            <div class="visual-card-grid">
                ${entries
                    .map(([item, count]) => {
                        const status = count >= 2 ? "keep" : "drop";
                        const width = Math.round((count / max) * 100);
                        return `
                            <div class="visual-item-card ${options.forceClass || status}">
                                <strong>${item}</strong>
                                <span>count = ${count}</span>
                                <i style="--w:${width}%"></i>
                            </div>
                        `;
                    })
                    .join("")}
            </div>
        `;
    }

    function renderAprioriSingles() {
        // Apriori 第一步：扫描 C1。
        visualCanvas.innerHTML = `
            <div class="visual-section-title">C1 候选 1 项集支持度扫描</div>
            ${itemCards(Object.entries(supportCounts).sort((a, b) => b[1] - a[1]))}
        `;
    }

    function renderAprioriL1() {
        // Apriori 第二步：根据最小支持度得到 L1。
        visualCanvas.innerHTML = `
            <div class="visual-section-title">L1 = 保留 count ≥ 2 的商品</div>
            ${itemCards(Object.entries(supportCounts).sort((a, b) => b[1] - a[1]))}
            <div class="candidate-output">
                <span>L1</span>
                ${frequentItemNames.map((item) => `<b>${item}</b>`).join("")}
            </div>
        `;
    }

    function renderAprioriPairs() {
        // Apriori 第三步：由 L1 连接生成 C2 并剪枝。
        visualCanvas.innerHTML = `
            <div class="visual-section-title">C2 候选二项集与 L2 剪枝</div>
            <div class="pair-matrix">
                ${Object.entries(pairCounts)
                    .map(([key, count]) => `
                        <div class="${count >= 2 ? "keep" : "drop"}">
                            <strong>${key.replace("+", " + ")}</strong>
                            <span>count = ${count}</span>
                        </div>
                    `)
                    .join("")}
            </div>
        `;
    }

    function renderAprioriRules() {
        // Apriori 第四步：从频繁项集拆分前件和后件生成规则。
        visualCanvas.innerHTML = `
            <div class="visual-section-title">从频繁项集生成规则</div>
            <div class="rule-demo-grid">
                <div class="rule-demo-card">
                    <span>频繁项集</span>
                    <strong>{牛奶, 面包}</strong>
                    <p>support = 3 / 5 = 60%</p>
                </div>
                <div class="rule-arrow">→</div>
                <div class="rule-demo-card keep">
                    <span>规则</span>
                    <strong>牛奶 → 面包</strong>
                    <p>confidence = 3 / 4 = 75%</p>
                    <p>lift = 0.75 / 0.80 = 0.94</p>
                </div>
                <div class="rule-demo-card keep">
                    <span>高 lift 示例</span>
                    <strong>尿布 → 啤酒</strong>
                    <p>confidence = 2 / 2 = 100%</p>
                    <p>lift = 1.00 / 0.40 = 2.50</p>
                </div>
            </div>
        `;
    }

    function fpOrder() {
        // FP-Growth 的全局频率排序。
        return [...frequentItems].sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0])).map(([item]) => item);
    }

    function sortedDemoTransactions() {
        // 根据全局频率顺序重排每条交易。
        const order = fpOrder();
        return demoTransactions.map((transaction) => ({
            id: transaction.id,
            items: transaction.items.filter((item) => order.includes(item)).sort((a, b) => order.indexOf(a) - order.indexOf(b)),
        }));
    }

    function renderFPSingles() {
        // FP-Growth 第一步：构造 header table。
        visualCanvas.innerHTML = `
            <div class="visual-section-title">单项频率排序 Header Table</div>
            <div class="header-table-demo">
                ${fpOrder()
                    .map((item, index) => `
                        <div>
                            <span>#${index + 1}</span>
                            <strong>${item}</strong>
                            <em>${supportCounts[item]}</em>
                        </div>
                    `)
                    .join("")}
            </div>
        `;
    }

    function renderFPSortedTransactions() {
        // FP-Growth 第二步：展示排序后的交易路径。
        visualCanvas.innerHTML = `
            <div class="visual-section-title">按频率顺序重排交易</div>
            <div class="sorted-transaction-list">
                ${sortedDemoTransactions()
                    .map((transaction) => `
                        <div>
                            <strong>${transaction.id}</strong>
                            <span>${transaction.items.map((item) => `<i>${item}</i>`).join("")}</span>
                        </div>
                    `)
                    .join("")}
            </div>
        `;
    }

    function renderFPTree() {
        // FP-Growth 第三步：用 SVG 展示共享前缀树。
        visualCanvas.innerHTML = `
            <div class="visual-section-title">FP-Tree 共享前缀路径</div>
            <svg class="fp-tree-svg" viewBox="0 0 760 420" role="img" aria-label="FP tree visualization">
                <line x1="380" y1="52" x2="270" y2="135" />
                <line x1="380" y1="52" x2="500" y2="135" />
                <line x1="270" y1="135" x2="210" y2="230" />
                <line x1="270" y1="135" x2="330" y2="230" />
                <line x1="500" y1="135" x2="500" y2="230" />
                <line x1="210" y1="230" x2="160" y2="325" />
                <line x1="330" y1="230" x2="390" y2="325" />
                ${treeNode(380, 52, "ROOT", "")}
                ${treeNode(270, 135, "牛奶", "4")}
                ${treeNode(500, 135, "面包", "1")}
                ${treeNode(210, 230, "面包", "3")}
                ${treeNode(330, 230, "尿布", "1")}
                ${treeNode(500, 230, "黄油", "1")}
                ${treeNode(160, 325, "黄油", "2")}
                ${treeNode(390, 325, "啤酒", "1")}
            </svg>
        `;
    }

    function treeNode(x, y, label, count) {
        // SVG 树节点模板。
        return `
            <g class="tree-node">
                <rect x="${x - 54}" y="${y - 26}" width="108" height="52" rx="4"></rect>
                <text x="${x}" y="${y - 2}" text-anchor="middle">${label}</text>
                <text x="${x}" y="${y + 17}" text-anchor="middle">${count ? `count ${count}` : ""}</text>
            </g>
        `;
    }

    function renderFPConditional() {
        // FP-Growth 第四步：展示条件模式基。
        visualCanvas.innerHTML = `
            <div class="visual-section-title">以“黄油”为后缀的条件模式基</div>
            <div class="conditional-demo">
                <div class="path-card">
                    <span>路径 1</span>
                    <strong>牛奶 → 面包 → 黄油</strong>
                    <em>count = 2</em>
                </div>
                <div class="path-card">
                    <span>路径 2</span>
                    <strong>面包 → 黄油</strong>
                    <em>count = 1</em>
                </div>
                <div class="candidate-output">
                    <span>条件模式</span>
                    <b>{面包, 黄油}</b>
                    <b>{牛奶, 面包, 黄油}</b>
                </div>
            </div>
        `;
    }

    function tidsets() {
        // Eclat 的垂直 TID-set 转换。
        const sets = {};
        Object.keys(supportCounts).forEach((item) => {
            sets[item] = demoTransactions.filter((transaction) => transaction.items.includes(item)).map((transaction) => transaction.id);
        });
        return sets;
    }

    function renderEclatTidsets() {
        // Eclat 第一步：展示每个商品对应的交易 ID 集合。
        const sets = tidsets();
        visualCanvas.innerHTML = `
            <div class="visual-section-title">水平数据 → 垂直 TID-set</div>
            <div class="tidset-grid">
                ${Object.entries(sets)
                    .map(([item, tids]) => `
                        <div class="${tids.length >= 2 ? "keep" : "drop"}">
                            <strong>${item}</strong>
                            <span>${tids.map((tid) => `<i>${tid}</i>`).join("")}</span>
                        </div>
                    `)
                    .join("")}
            </div>
        `;
    }

    function renderEclatIntersection() {
        // Eclat 第二步：用集合交集解释组合项集支持度。
        visualCanvas.innerHTML = `
            <div class="visual-section-title">TID-set 交集直接得到支持度</div>
            <div class="intersection-demo">
                <div class="set-card">
                    <strong>牛奶</strong>
                    <span><i>T1</i><i>T2</i><i>T4</i><i>T5</i></span>
                </div>
                <div class="intersect-symbol">∩</div>
                <div class="set-card">
                    <strong>面包</strong>
                    <span><i>T1</i><i>T2</i><i>T3</i><i>T5</i></span>
                </div>
                <div class="intersect-symbol">=</div>
                <div class="set-card keep">
                    <strong>{牛奶, 面包}</strong>
                    <span><i>T1</i><i>T2</i><i>T5</i></span>
                    <em>count = 3</em>
                </div>
            </div>
        `;
    }

    function renderEclatPrefix() {
        // Eclat 第三步：展示前缀递归扩展。
        visualCanvas.innerHTML = `
            <div class="visual-section-title">前缀递归扩展示意</div>
            <div class="prefix-tree">
                <div class="prefix-node root keep">∅ 起始前缀</div>
                <div class="prefix-row">
                    <div class="prefix-node keep">牛奶 {T1,T2,T4,T5}</div>
                    <div class="prefix-node keep">面包 {T1,T2,T3,T5}</div>
                    <div class="prefix-node keep">黄油 {T1,T3,T5}</div>
                </div>
                <div class="prefix-row">
                    <div class="prefix-node keep">牛奶,面包 {T1,T2,T5}</div>
                    <div class="prefix-node keep">牛奶,黄油 {T1,T5}</div>
                    <div class="prefix-node drop">尿布,黄油 ∅</div>
                </div>
            </div>
        `;
    }

    function renderEclatRules() {
        // Eclat 第四步：展示频繁项集到规则的输出。
        visualCanvas.innerHTML = `
            <div class="visual-section-title">Eclat 输出和规则计算</div>
            <div class="rule-demo-grid">
                <div class="rule-demo-card keep">
                    <span>频繁项集</span>
                    <strong>{牛奶, 面包}</strong>
                    <p>TID = {T1,T2,T5}</p>
                    <p>support = 3 / 5</p>
                </div>
                <div class="rule-demo-card keep">
                    <span>频繁项集</span>
                    <strong>{尿布, 啤酒}</strong>
                    <p>TID = {T2,T4}</p>
                    <p>support = 2 / 5</p>
                </div>
                <div class="rule-demo-card keep">
                    <span>规则</span>
                    <strong>尿布 → 啤酒</strong>
                    <p>confidence = 100%</p>
                    <p>lift = 2.50</p>
                </div>
            </div>
        `;
    }
});
