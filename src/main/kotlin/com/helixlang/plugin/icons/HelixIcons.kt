package com.helixlang.plugin.icons

import com.intellij.openapi.util.IconLoader

object HelixIcons {
    @JvmField
    val FILE: javax.swing.Icon = IconLoader.getIcon("/icons/helix.svg", HelixIcons::class.java)

    @JvmField
    val GENE: javax.swing.Icon = IconLoader.getIcon("/icons/gene.svg", HelixIcons::class.java)

    @JvmField
    val PROMOTER: javax.swing.Icon = IconLoader.getIcon("/icons/promoter.svg", HelixIcons::class.java)
}
