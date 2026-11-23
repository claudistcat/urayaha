package com.claudecat.urayaha.alarm

/**
 * bridge.py の set_opener() へ渡す、「対象を開く」処理そのもの。
 * ADR-0005: ウロル.イヤッハー(対象) が何をどう開くかはホスト(Kotlin)の責任。
 */
interface Opener {
    fun open(target: String)
}
