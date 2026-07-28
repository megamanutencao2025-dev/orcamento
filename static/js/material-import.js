(() => {
    const form = document.querySelector("#material-import-form");
    if (!form) return;

    const urlInput = document.querySelector("#product-url");
    const searchButton = document.querySelector("#import-search-button");
    const buttonLabel = searchButton.querySelector(".button-label");
    const feedback = document.querySelector("#import-feedback");
    const preview = document.querySelector("#import-preview");
    const previewImage = document.querySelector("#import-preview-image");
    const previewPlaceholder = document.querySelector("#import-preview-placeholder");
    const useButton = document.querySelector("#use-imported-product");
    const purchaseType = document.querySelector("#id_forma_compra");
    const purchasePrice = document.querySelector("#id_preco_compra");
    const boxQuantity = document.querySelector(
        "#id_quantidade_unidades_caixa",
    );
    const calculatedUnitPrice = document.querySelector(
        "#id_preco_unitario_calculado",
    );
    const purchasePriceLabel = document.querySelector(
        'label[for="id_preco_compra"]',
    );
    const boxFields = document.querySelectorAll("[data-box-field]");
    let product = null;

    const setFeedback = (message = "", kind = "info") => {
        feedback.textContent = message;
        feedback.className = message
            ? `import-feedback is-visible is-${kind}`
            : "import-feedback";
    };

    const setLoading = (loading) => {
        searchButton.classList.toggle("is-loading", loading);
        searchButton.disabled = loading;
        buttonLabel.textContent = loading ? "Buscando..." : "Buscar produto";
    };

    const formatPrice = (value) => {
        if (value === null || value === "") return "Preço não encontrado";
        return new Intl.NumberFormat("pt-BR", {
            style: "currency",
            currency: "BRL",
        }).format(Number(value));
    };

    const parseDecimal = (value) => {
        const parsed = Number(String(value).trim().replace(",", "."));
        return Number.isFinite(parsed) ? parsed : null;
    };

    const updateCalculatedUnitPrice = () => {
        if (!purchaseType || !purchasePrice || !calculatedUnitPrice) return;

        const price = parseDecimal(purchasePrice.value);
        if (price === null || price < 0) {
            calculatedUnitPrice.value = "";
            return;
        }

        if (purchaseType.value === "unidade") {
            calculatedUnitPrice.value = price.toFixed(2);
            return;
        }

        const quantity = parseDecimal(boxQuantity?.value);
        if (quantity === null || !Number.isInteger(quantity) || quantity <= 0) {
            calculatedUnitPrice.value = "";
            return;
        }

        const priceInCents = Math.round(price * 100);
        const unitPriceInCents = Math.floor(
            ((2 * priceInCents) + quantity) / (2 * quantity),
        );
        calculatedUnitPrice.value = (unitPriceInCents / 100).toFixed(2);
    };

    const updatePurchaseFields = () => {
        if (!purchaseType) return;

        const isBox = purchaseType.value === "caixa";
        boxFields.forEach((field) => {
            field.hidden = !isBox;
        });

        if (boxQuantity) {
            boxQuantity.disabled = !isBox;
            boxQuantity.required = isBox;
            if (isBox) {
                boxQuantity.setAttribute("aria-required", "true");
            } else {
                boxQuantity.removeAttribute("aria-required");
                boxQuantity.setCustomValidity("");
            }
        }

        if (purchasePriceLabel) {
            purchasePriceLabel.textContent = isBox
                ? "Preço da caixa"
                : "Preço unitário";
        }

        updateCalculatedUnitPrice();
    };

    const showPreview = (data) => {
        product = data;
        document.querySelector("#import-preview-store").textContent = data.supplier;
        document.querySelector("#import-preview-confidence").textContent =
            `Confiança ${data.confidence}`;
        document.querySelector("#import-preview-name").textContent = data.name;
        document.querySelector("#import-preview-price").textContent =
            formatPrice(data.price);
        document.querySelector("#import-preview-source").textContent =
            `Valor encontrado em ${data.source}. Ao aplicar, ele será tratado como preço da unidade ou da caixa conforme a forma de compra.`;

        const warnings = document.querySelector("#import-preview-warnings");
        warnings.replaceChildren();
        data.warnings.forEach((warning) => {
            const item = document.createElement("li");
            item.textContent = warning;
            warnings.appendChild(item);
        });

        previewImage.hidden = !data.image_url;
        previewPlaceholder.hidden = Boolean(data.image_url);
        if (data.image_url) {
            previewImage.src = data.image_url;
            previewImage.alt = data.name;
        } else {
            previewImage.removeAttribute("src");
        }
        preview.hidden = false;
    };

    previewImage.addEventListener("error", () => {
        previewImage.hidden = true;
        previewPlaceholder.hidden = false;
    });

    purchaseType?.addEventListener("change", updatePurchaseFields);
    purchasePrice?.addEventListener("input", updateCalculatedUnitPrice);
    boxQuantity?.addEventListener("input", updateCalculatedUnitPrice);
    updatePurchaseFields();

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!form.reportValidity()) return;
        setFeedback();
        preview.hidden = true;
        setLoading(true);
        try {
            const response = await fetch(form.dataset.endpoint, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": form.querySelector(
                        "[name=csrfmiddlewaretoken]",
                    ).value,
                },
                body: JSON.stringify({ url: urlInput.value }),
            });
            const result = await response.json();
            if (!response.ok || !result.ok) {
                throw new Error(result.error || "Não foi possível buscar o produto.");
            }
            showPreview(result.product);
            setFeedback(
                "Produto encontrado. Confira a prévia e escolha “Usar estes dados”.",
                "info",
            );
        } catch (error) {
            setFeedback(error.message, "error");
        } finally {
            setLoading(false);
        }
    });

    useButton.addEventListener("click", () => {
        if (!product) return;
        document.querySelector("#id_nome").value = product.name || "";
        purchasePrice.value = product.price ?? "";
        document.querySelector("#id_fornecedor").value = product.supplier || "";
        document.querySelector("#id_imagem_url").value = product.image_url || "";
        document.querySelector("#id_url_origem").value = product.source_url || "";
        document.querySelector("#id_fonte_importacao").value = product.supplier || "";
        document.querySelector("#import-origin-note").hidden = false;
        updateCalculatedUnitPrice();
        document.querySelector("#cadastro-form").scrollIntoView({
            behavior: "smooth",
            block: "start",
        });
        purchaseType?.focus();
        setFeedback(
            "Dados aplicados. Confira a forma de compra, a categoria, a unidade de medida e o tipo de uso antes de salvar.",
            "info",
        );
    });
})();
