package com.helixlang.plugin.lsp.handlers

import com.helixlang.plugin.filetype.HelixLanguage
import com.helixlang.plugin.lsp.HelixLspServerManager
import com.helixlang.plugin.lsp.protocol.LspConstants
import com.helixlang.plugin.settings.HelixSettings
import com.intellij.codeInsight.completion.CompletionContributor
import com.intellij.codeInsight.completion.CompletionParameters
import com.intellij.codeInsight.completion.CompletionResultSet
import com.intellij.codeInsight.completion.InsertHandler
import com.intellij.codeInsight.lookup.LookupElement
import com.intellij.codeInsight.lookup.LookupElementBuilder
import com.intellij.openapi.project.DumbAware

/**
 * Completion via `textDocument/completion` (doc/04 §5.3). When the server is
 * unavailable, a static fallback list of annotation kinds and field names keeps
 * `#` completion working.
 */
class HelixCompletionContributor : CompletionContributor(), DumbAware {

    override fun fillCompletionVariants(parameters: CompletionParameters, result: CompletionResultSet) {
        val position = parameters.position
        if (position.containingFile.language != HelixLanguage) return
        val offset = parameters.offset
        val line = parameters.editor.document.getLineNumber(offset)
        val character = offset - parameters.editor.document.getLineStartOffset(line)
        val fileUri = com.intellij.openapi.fileEditor.FileDocumentManager.getInstance()
            .getFile(parameters.editor.document)?.url

        val server = parameters.editor.project
            ?.getService(HelixLspServerManager::class.java)

        if (server != null && server.isReady && fileUri != null) {
            server.request(
                LspConstants.COMPLETION,
                com.helixlang.plugin.lsp.protocol.LspMessages.requestPosition(
                    LspConstants.COMPLETION, fileUri, line, character),
                1500,
            ).whenComplete { completed, error ->
                if (error != null || completed == null) {
                    addFallback(result)
                    return@whenComplete
                }
                val items = try {
                    completed.getAsJsonObject("result").getAsJsonArray("items")
                } catch (_: Exception) {
                    null
                }
                if (items == null) {
                    addFallback(result)
                    return@whenComplete
                }
                for (item in items) {
                    if (item.isJsonObject) result.addElement(mapItem(item.asJsonObject))
                }
            }
            return
        }

        addFallback(result)
    }

    private fun addFallback(result: CompletionResultSet) {
        if (HelixSettings.getInstance().completionFallbackEnabled) {
            for (item in STATIC_ITEMS) result.addElement(item)
        }
    }

    private fun mapItem(item: com.google.gson.JsonObject): LookupElement {
        val label = item.get("label")?.asString ?: ""
        val kind = item.get("kind")?.asInt ?: 0
        val text = item.get("insertText")?.asString ?: label
        return LookupElementBuilder.create(text)
            .withLookupString(label)
            .withTypeText(kindLabel(kind), true)
    }

    private fun kindLabel(kind: Int): String = when (kind) {
        3 -> "function"
        14 -> "keyword"
        1 -> "text"
        else -> ""
    }

    companion object {
        private val ANNOTATION_KINDS = listOf(
            "gene", "promoter", "regulate", "lsystem", "field", "config", "type",
            "crispr", "evolve", "methylate", "histone", "transcribe", "translate",
            "quorum", "media", "enzyme", "metabolite", "sim", "genome",
            "morphogen", "species", "patch", "gem", "end")

        private val FIELD_NAMES = listOf(
            "name", "promoter", "call_target", "strength", "target", "axiom",
            "rules", "ticks", "output", "table", "species", "units",
            "nutrient", "concentration", "diffusion_um2_s", "gene", "reaction",
            "kcat", "init", "backend", "seed", "division_rule",
            "replication_mode", "protein_maturation_mode", "mechanics", "kind",
            "source", "tf_map", "grn_mode", "active_gene_budget", "channel",
            "gain", "replicon", "replicons", "photo", "photo_vmax", "cn_ratio",
            "maintenance", "substrate", "vmax", "ks", "substrate2", "vmax2",
            "ks2", "secretion", "diet", "attack", "width", "height",
            "carrying_capacity", "anoxic", "moisture", "clay", "cn_som",
            "cn_species", "initial_nh4_mm", "initial_no3_mm", "flow_rate",
            "fluctuation_period", "fluctuation_amplitude", "dispersal",
            "fast_forward", "scheduler_max_step", "community_fba",
            "sample_every", "generations", "evaluation_ticks",
            "evolution_enabled", "stress_field", "stress_level", "n_rounds",
            "substrate_mm", "target_protein", "mutation_rate", "bias_fraction",
            "n_candidates", "organism", "genome", "use_database",
            "include_spontaneous", "gapfill", "target_organism", "medium",
            "dynamic", "duration", "dt", "expression", "use_full_model",
            "gem_driven")

        private val STATIC_ITEMS: List<LookupElement> =
            ANNOTATION_KINDS.map { kind ->
                LookupElementBuilder.create(kind)
                    .withTypeText("annotation", true)
            } + FIELD_NAMES.map { field ->
                LookupElementBuilder.create(field)
                    .withTypeText("field", true)
            }
    }
}
