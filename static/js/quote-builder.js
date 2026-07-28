(() => {
    const form = document.querySelector("#quote-form");
    if (!form) return;

    const parseJson = (id) => {
        const element = document.querySelector(`#${id}`);
        return element ? JSON.parse(element.textContent) : {};
    };
    const catalogs = parseJson("quote-catalogs");
    const initial = parseJson("quote-initial-items");
    const state = {
        materials: initial.materials || [],
        clientMaterials: initial.clientMaterials || [],
        supplies: initial.supplies || [],
        services: initial.services || [],
        otherCosts: initial.otherCosts || [],
    };

    const money = new Intl.NumberFormat("pt-BR", {
        style: "currency",
        currency: "BRL",
    });
    const number = (value) => {
        const parsed = Number(String(value ?? 0).replace(",", "."));
        return Number.isFinite(parsed) ? parsed : 0;
    };
    const formatNumber = (value) =>
        new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 3 }).format(number(value));
    const escapeHtml = (value) =>
        String(value ?? "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");
    const byId = (collection, id) =>
        (collection || []).find((item) => String(item.id) === String(id));
    const input = (id) => document.querySelector(`#${id}`);
    const value = (id) => input(id)?.value.trim() || "";
    const announce = (message) => {
        const status = input("builder-status");
        if (!status) return;
        status.textContent = "";
        window.requestAnimationFrame(() => {
            status.textContent = message;
        });
    };

    const sectionStorageKey = "quote-builder:sections";
    let savedSections = {};
    try {
        savedSections = JSON.parse(sessionStorage.getItem(sectionStorageKey) || "{}");
    } catch {
        savedSections = {};
    }
    form.querySelectorAll("[data-section-key]").forEach((section) => {
        const key = section.dataset.sectionKey;
        if (Object.hasOwn(savedSections, key)) section.open = savedSections[key];
        section.addEventListener("toggle", () => {
            savedSections[key] = section.open;
            try {
                sessionStorage.setItem(sectionStorageKey, JSON.stringify(savedSections));
            } catch {
                // A interface continua funcional quando o armazenamento está indisponível.
            }
        });
    });
    form.querySelectorAll(".field__error, .errorlist").forEach((error) => {
        const section = error.closest("details");
        if (section) section.open = true;
    });

    function requireFields(fields) {
        for (const [id, message] of fields) {
            const element = input(id);
            if (!element || !element.value || (element.type === "number" && number(element.value) <= 0)) {
                element?.setCustomValidity(message);
                element?.reportValidity();
                element?.addEventListener("input", () => element.setCustomValidity(""), { once: true });
                return false;
            }
        }
        return true;
    }

    function resetFields(ids) {
        ids.forEach((id) => {
            const element = input(id);
            if (!element) return;
            if (element.tagName === "SELECT") element.selectedIndex = 0;
            else if (element.type === "number") element.value = id.endsWith("qty") ? "1" : "0";
            else element.value = "";
        });
    }

    function modifierPercent(item, key, catalogKey) {
        const option = byId(catalogs[catalogKey], item[key]);
        return option ? number(option.percentual) : 0;
    }

    function materialTotal(item) {
        return number(item.quantity) * number(item.unitPrice);
    }

    function serviceValues(item) {
        const base = number(item.quantity) * number(item.unitPrice);
        const difficulty = base * modifierPercent(item, "difficultyId", "difficulties") / 100;
        const height = base * modifierPercent(item, "heightId", "heights") / 100;
        return { base, difficulty, height, total: base + difficulty + height };
    }

    function removeButton(section, index, label) {
        return `<button class="builder-remove" type="button" data-remove="${section}" data-index="${index}" aria-label="Remover ${escapeHtml(label)}">×</button>`;
    }

    const renderers = {
        materials: (item, index) => {
            const catalog = byId(catalogs.materials, item.catalogId);
            const nome = catalog?.nome || "Material";
            return `<tr>
                <th scope="row">${escapeHtml(nome)}</th>
                <td class="align-right">${formatNumber(item.quantity)}</td>
                <td>${escapeHtml(item.unit)}</td>
                <td class="align-right">${money.format(number(item.unitPrice))}</td>
                <td>${escapeHtml(item.supplier || "—")}</td>
                <td class="align-right"><strong>${money.format(materialTotal(item))}</strong></td>
                <td>${removeButton("materials", index, nome)}</td>
            </tr>`;
        },
        clientMaterials: (item, index) => `<tr>
            <th scope="row">${escapeHtml(item.description)}</th>
            <td class="align-right">${formatNumber(item.quantity)}</td>
            <td>${escapeHtml(item.unit)}</td>
            <td>${escapeHtml(item.note || "—")}</td>
            <td>${removeButton("clientMaterials", index, item.description)}</td>
        </tr>`,
        supplies: (item, index) => {
            const catalog = byId(catalogs.materials, item.catalogId);
            const nome = catalog?.nome || "Insumo";
            return `<tr>
                <th scope="row">${escapeHtml(nome)}</th>
                <td class="align-right">${formatNumber(item.quantity)}</td>
                <td>${escapeHtml(item.unit)}</td>
                <td class="align-right">${money.format(number(item.unitPrice))}</td>
                <td class="align-right"><strong>${money.format(materialTotal(item))}</strong></td>
                <td>${removeButton("supplies", index, nome)}</td>
            </tr>`;
        },
        services: (item, index) => {
            const catalog = byId(catalogs.services, item.serviceId);
            const difficulty = byId(catalogs.difficulties, item.difficultyId);
            const height = byId(catalogs.heights, item.heightId);
            const values = serviceValues(item);
            const nome = catalog?.nome || "Serviço";
            return `<tr>
                <th scope="row">${escapeHtml(nome)}<small>${escapeHtml(catalog?.unidade || "")}</small></th>
                <td class="align-right">${formatNumber(item.quantity)}</td>
                <td class="align-right">${money.format(number(item.unitPrice))}</td>
                <td>${escapeHtml(difficulty?.nome || "Sem acréscimo")}<small>+ ${money.format(values.difficulty)}</small></td>
                <td>${escapeHtml(height?.nome || "Sem acréscimo")}<small>+ ${money.format(values.height)}</small></td>
                <td class="align-right"><strong>${money.format(values.total)}</strong></td>
                <td>${removeButton("services", index, nome)}</td>
            </tr>`;
        },
        otherCosts: (item, index) => `<tr>
            <th scope="row">${escapeHtml(item.description)}</th>
            <td class="align-right"><strong>${money.format(number(item.value))}</strong></td>
            <td>${removeButton("otherCosts", index, item.description)}</td>
        </tr>`,
    };

    function setText(selector, text) {
        document.querySelectorAll(selector).forEach((element) => {
            element.textContent = text;
        });
    }

    function totals() {
        const materials = state.materials.reduce((sum, item) => sum + materialTotal(item), 0);
        const supplies = state.supplies.reduce((sum, item) => sum + materialTotal(item), 0);
        const serviceTotals = state.services.reduce(
            (sum, item) => {
                const values = serviceValues(item);
                return {
                    base: sum.base + values.base,
                    difficulty: sum.difficulty + values.difficulty,
                    height: sum.height + values.height,
                    total: sum.total + values.total,
                };
            },
            { base: 0, difficulty: 0, height: 0, total: 0 },
        );
        const otherCosts = state.otherCosts.reduce((sum, item) => sum + number(item.value), 0);
        const vehicle = byId(catalogs.vehicles, document.querySelector("#id_veiculo")?.value);
        const distance = number(document.querySelector("#id_distancia_km")?.value);
        const transport = vehicle && number(vehicle.km_por_litro) > 0
            ? distance / number(vehicle.km_por_litro) * number(vehicle.preco_combustivel)
            : 0;
        const methodElement = document.querySelector("#id_metodo_mao_obra");
        const isServices = methodElement?.value === "servicos";
        const labor = isServices
            ? serviceTotals.total
            : number(document.querySelector("#id_tempo_estimado_horas")?.value)
                * number(document.querySelector("#id_valor_hora")?.value);
        const directCosts = materials + supplies + transport + otherCosts;
        const tools = labor * number(document.querySelector("#id_percentual_ferramentas")?.value) / 100;
        const operational = directCosts + labor + tools;
        const company = operational * number(document.querySelector("#id_percentual_empresa")?.value) / 100;
        const beforeProfit = operational + company;
        const profit = beforeProfit * number(document.querySelector("#id_percentual_lucro")?.value) / 100;
        const beforeDiscount = beforeProfit + profit;
        const discount = number(document.querySelector("#id_desconto")?.value);
        return {
            materials,
            supplies,
            servicesBase: serviceTotals.base,
            difficulty: serviceTotals.difficulty,
            height: serviceTotals.height,
            services: serviceTotals.total,
            transport,
            otherCosts,
            directCosts,
            labor,
            tools,
            company,
            profit,
            beforeDiscount,
            discount,
            final: beforeDiscount - discount,
            laborMethod: methodElement?.selectedOptions[0]?.textContent || "",
        };
    }

    function render() {
        Object.keys(state).forEach((section) => {
            const container = document.querySelector(`[data-items="${section}"]`);
            const hasItems = state[section].length > 0;
            if (container) {
                container.innerHTML = state[section].map(renderers[section]).join("");
            }
            const tableWrap = document.querySelector(`[data-table-wrap="${section}"]`);
            if (tableWrap) tableWrap.hidden = !hasItems;
            const empty = document.querySelector(`[data-empty="${section}"]`);
            if (empty) empty.hidden = hasItems;
        });

        const result = totals();
        ["materials", "supplies", "services", "otherCosts"].forEach((key) => {
            setText(`[data-section-total="${key}"]`, money.format(result[key]));
        });
        setText("[data-section-count='clientMaterials']", `${state.clientMaterials.length} ${state.clientMaterials.length === 1 ? "item" : "itens"}`);
        Object.entries(result).forEach(([key, total]) => {
            setText(`[data-summary="${key}"]`, key === "laborMethod" ? total : money.format(total));
        });
        setText("[data-summary='clientCount']", `${state.clientMaterials.length} ${state.clientMaterials.length === 1 ? "item" : "itens"}`);

        const isTime = document.querySelector("#id_metodo_mao_obra")?.value === "tempo";
        document.querySelectorAll("[data-time-field]").forEach((field) => {
            field.classList.toggle("is-muted", !isTime);
        });
    }

    function addMaterial() {
        if (!requireFields([["material-catalog", "Selecione um material."], ["material-qty", "A quantidade deve ser maior que zero."]])) return;
        state.materials.push({
            catalogId: value("material-catalog"),
            quantity: value("material-qty"),
            unit: value("material-unit"),
            unitPrice: value("material-price"),
            supplier: value("material-supplier"),
        });
        resetFields(["material-catalog", "material-qty", "material-unit", "material-price", "material-supplier"]);
    }

    function addClientMaterial() {
        if (!requireFields([["client-description", "Informe a descrição do material."], ["client-qty", "A quantidade deve ser maior que zero."], ["client-unit", "Informe a unidade."]])) return;
        const reference = catalogs.materials.find(
            (item) => item.nome.toLocaleLowerCase("pt-BR") === value("client-description").toLocaleLowerCase("pt-BR"),
        );
        state.clientMaterials.push({
            referenceId: reference?.id || null,
            description: value("client-description"),
            quantity: value("client-qty"),
            unit: value("client-unit"),
            note: value("client-note"),
        });
        resetFields(["client-description", "client-qty", "client-unit", "client-note"]);
    }

    function addSupply() {
        if (!requireFields([["supply-catalog", "Selecione um insumo."], ["supply-qty", "A quantidade deve ser maior que zero."]])) return;
        state.supplies.push({
            catalogId: value("supply-catalog"),
            quantity: value("supply-qty"),
            unit: value("supply-unit"),
            unitPrice: value("supply-price"),
        });
        resetFields(["supply-catalog", "supply-qty", "supply-unit", "supply-price"]);
    }

    function addService() {
        if (!requireFields([["service-catalog", "Selecione um serviço."], ["service-qty", "A quantidade deve ser maior que zero."]])) return;
        state.services.push({
            serviceId: value("service-catalog"),
            quantity: value("service-qty"),
            unitPrice: value("service-price"),
            difficultyId: value("service-difficulty") || null,
            heightId: value("service-height") || null,
        });
        resetFields(["service-catalog", "service-qty", "service-price", "service-difficulty", "service-height"]);
    }

    function addCost() {
        if (!requireFields([["cost-description", "Informe a descrição do custo."]])) return;
        const costValue = number(value("cost-value"));
        if (costValue < 0) return;
        state.otherCosts.push({ description: value("cost-description"), value: costValue });
        resetFields(["cost-description", "cost-value"]);
        input("other-cost-entry").hidden = true;
    }

    const adders = {
        materials: addMaterial,
        clientMaterials: addClientMaterial,
        supplies: addSupply,
        services: addService,
        otherCosts: addCost,
    };

    document.querySelectorAll("[data-add]").forEach((button) => {
        button.addEventListener("click", () => {
            const quantidadeAnterior = state[button.dataset.add].length;
            adders[button.dataset.add]();
            render();
            if (state[button.dataset.add].length > quantidadeAnterior) {
                announce("Item adicionado.");
            }
        });
    });

    form.addEventListener("click", (event) => {
        const button = event.target.closest("[data-remove]");
        if (!button) return;
        const section = button.dataset.remove;
        const index = Number(button.dataset.index);
        state[section].splice(index, 1);
        render();
        announce("Item removido.");
        const proximoIndice = Math.min(index, state[section].length - 1);
        const proximoBotao = proximoIndice >= 0
            ? form.querySelector(`[data-remove="${section}"][data-index="${proximoIndice}"]`)
            : section === "otherCosts"
                ? input("toggle-cost")
                : form.querySelector(`[data-add="${section}"]`);
        proximoBotao?.focus();
    });

    const fillCatalog = (selectId, collection, mappings) => {
        input(selectId)?.addEventListener("change", (event) => {
            const selected = byId(catalogs[collection], event.target.value);
            if (!selected) return;
            Object.entries(mappings).forEach(([target, source]) => {
                input(target).value = selected[source] ?? "";
            });
        });
    };
    fillCatalog("material-catalog", "materials", {
        "material-unit": "unidade",
        "material-price": "preco_unitario",
        "material-supplier": "fornecedor",
    });
    fillCatalog("supply-catalog", "materials", {
        "supply-unit": "unidade",
        "supply-price": "preco_unitario",
    });
    fillCatalog("service-catalog", "services", { "service-price": "preco_unitario" });

    input("client-description")?.addEventListener("change", () => {
        const selected = catalogs.materials.find(
            (item) => item.nome.toLocaleLowerCase("pt-BR") === value("client-description").toLocaleLowerCase("pt-BR"),
        );
        if (selected) input("client-unit").value = selected.unidade;
    });

    input("toggle-cost")?.addEventListener("click", () => {
        input("other-cost-entry").hidden = false;
        input("cost-description").focus();
    });
    input("cancel-cost")?.addEventListener("click", () => {
        input("other-cost-entry").hidden = true;
    });

    [
        "id_veiculo",
        "id_distancia_km",
        "id_metodo_mao_obra",
        "id_tempo_estimado_horas",
        "id_valor_hora",
        "id_percentual_ferramentas",
        "id_percentual_empresa",
        "id_percentual_lucro",
        "id_desconto",
    ].forEach((id) => input(id)?.addEventListener("input", render));

    form.addEventListener("submit", (event) => {
        const hasItems = Object.values(state).some((items) => items.length > 0);
        if (!hasItems) {
            event.preventDefault();
            window.alert("Adicione ao menos um material, insumo, serviço ou outro custo.");
            return;
        }
        if (!form.checkValidity()) {
            event.preventDefault();
            const invalidField = form.querySelector(":invalid");
            const section = invalidField?.closest("details");
            if (section) section.open = true;
            invalidField?.focus();
            invalidField?.reportValidity();
            return;
        }
        const result = totals();
        if (result.discount > result.beforeDiscount) {
            event.preventDefault();
            const discountField = input("id_desconto");
            discountField?.setCustomValidity("O desconto não pode ser maior que o total.");
            discountField?.reportValidity();
            discountField?.addEventListener(
                "input",
                () => discountField.setCustomValidity(""),
                { once: true },
            );
            return;
        }
        input("itens-json").value = JSON.stringify(state);
    });

    render();
})();
