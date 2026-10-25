package com.example.sentinelhard.network

import com.example.sentinelhard.models.EnrolRequest
import com.example.sentinelhard.models.EnrolResponse
import com.example.sentinelhard.models.PaymentInfo
import com.example.sentinelhard.models.SessionResponse
import com.example.sentinelhard.models.VerifyRequest
import com.example.sentinelhard.models.VerifyResponse
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

interface BiometricApiService {

    /**
     * Submits the signed biometric payload for liveness validation and authentication.
     */
    @POST("auth/verify")
    suspend fun verifyBiometrics(@Body request: VerifyRequest): Response<VerifyResponse>

    /**
     * Polls the status of a specific session (useful if WebSockets drop).
     */
    @GET("sessions/{session_id}")
    suspend fun getSessionStatus(@Path("session_id") sessionId: String): Response<SessionResponse>

    /** SentinelSeal: the payment to show on the confirm screen before sealing. */
    @GET("payments/{payment_id}")
    suspend fun getPayment(@Path("payment_id") paymentId: String): Response<PaymentInfo>

    /** SentinelSeal: register this phone's StrongBox public key for an approver. */
    @POST("enrol")
    suspend fun enrol(@Body request: EnrolRequest): Response<EnrolResponse>
}
