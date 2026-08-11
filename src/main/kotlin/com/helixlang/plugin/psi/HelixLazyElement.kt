package com.helixlang.plugin.psi

import com.intellij.extapi.psi.ASTWrapperPsiElement
import com.intellij.lang.ASTNode

/** Placeholder PSI element for AST nodes (mini-PSI is lazy; rarely used). */
class HelixLazyElement(node: ASTNode) : ASTWrapperPsiElement(node)
