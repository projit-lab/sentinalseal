package com.example.sentinelhard.network

import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import java.util.concurrent.TimeUnit

/**
 * Singleton Retrofit client for communicating with the SentinelHard FastAPI backend.
 * Uses kotlinx.serialization for JSON conversion to match @Serializable data classes.
 */
object ApiClient {
    // SentinelSeal backend: uvicorn on the laptop, port 8000.
    // Physical phone: set this to the laptop's IP on the venue Wi-Fi (ipconfig on Windows).
    // Emulator: use "http://10.0.2.2:8000/api/v1/".
    private const val BASE_URL = "http://192.168.1.105:8000/api/v1/"

    // Lenient JSON parser: ignores unknown fields from server, encodes defaults
    private val json = Json {
        ignoreUnknownKeys = true
        encodeDefaults = true
    }

    // OkHttp with request/response body logging for debugging signed payloads
    private val okHttpClient = OkHttpClient.Builder()
        .addInterceptor(HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BODY
        })
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .build()

    val retrofit: Retrofit by lazy {
        Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(okHttpClient)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
    }

    val apiService: BiometricApiService by lazy {
        retrofit.create(BiometricApiService::class.java)
    }
}
