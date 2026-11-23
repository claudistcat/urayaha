package com.claudecat.urayaha.alarm

import android.content.Context
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File

/**
 * bridge.py(app/src/main/python/bridge.py)を呼ぶだけの薄いラッパー。
 * 「次は何時に鳴るか」「今回は何を再生するか」の判断は一切持たない。それは
 * alarm.ura(Runtime.run_file 経由)がやる。ここは Chaquopy の呼び出しを
 * 1 箇所にまとめているだけ。
 */
object UraBridge {

    private var bridgeModule: PyObject? = null

    @Synchronized
    fun init(context: Context) {
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(context.applicationContext))
        }
        if (bridgeModule == null) {
            bridgeModule = Python.getInstance().getModule("bridge")
        }
    }

    fun registerOpener(context: Context, opener: Opener) {
        init(context)
        bridgeModule!!.callAttr("set_opener", opener)
    }

    /** コマンド(argv)を 1 回分実行し、標準出力を返す。 */
    fun run(context: Context, argv: List<String>): String {
        init(context)
        val result = bridgeModule!!.callAttr(
            "run",
            context.filesDir.absolutePath,
            uraFile(context).absolutePath,
            *argv.toTypedArray()
        )
        return result.toString()
    }

    fun uraFile(context: Context): File = File(context.filesDir, "alarm.ura")

    /** assets の alarm.ura を filesDir へ上書きコピーする(alarm.json もそこに作られる)。 */
    fun syncScript(context: Context) {
        context.assets.open("alarm.ura").use { input ->
            uraFile(context).outputStream().use { output -> input.copyTo(output) }
        }
    }
}
