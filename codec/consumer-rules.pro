# The public Java API is called directly; avoid shrinking native JNI signatures.
-keep class com.enaskr.player.codec.CodecPack { *; }
-keep class com.enaskr.player.codec.CodecSession { *; }
-keep class com.enaskr.player.codec.CodecCatalog { *; }
