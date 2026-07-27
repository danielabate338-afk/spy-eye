# ProGuard rules for SpyEye Android Agent Obfuscation & Optimization

-keep class org.spyeye.agent.** { *; }
-dontwarn org.spyeye.agent.**

# Keep Kivy and Python-for-Android core bindings
-keep class org.kivy.android.** { *; }
-keep class org.renpy.android.** { *; }

# Optimization exclusions
-optimizations !code/simplification/arithmetic,!code/simplification/cast,!field/*,!class/merging/*
-allowaccessmodification

# Preserve line numbers for telemetry debugging if required
-keepattributes SourceFile,LineNumberTable