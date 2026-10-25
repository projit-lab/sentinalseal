package com.example.sentinelhard.models

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * Signed biometric payload sent to the backend for liveness verification.
 * Matches the FastAPI VerifyRequest schema.
 */
@Serializable
data class VerifyRequest(
    val payload: String,              // Base64-encoded JSON of BiometricPayload
    val signature: String,            // Base64 ECDSA signature of the payload
    @SerialName("public_key")
    val publicKey: String,            // Base64 DER-encoded SubjectPublicKeyInfo
    @SerialName("attestation_chain")
    val attestationChain: List<String> = emptyList()  // X.509 cert chain (leaf → root)
)

/**
 * Raw biometric telemetry data, serialized to JSON then signed.
 */
@Serializable
data class BiometricPayload(
    @SerialName("session_id")
    val sessionId: String,
    val bpm: Double,
    val timestamp: String,            // ISO-8601
    @SerialName("device_id")
    val deviceId: String,
    val snr: Double,
    val variance: Double
)

/**
 * Backend response after verifying biometric data.
 */
@Serializable
data class VerifyResponse(
    val status: String,
    @SerialName("session_id")
    val sessionId: String,
    val reason: String? = null,
    @SerialName("payment_id") val paymentId: String? = null,
    @SerialName("payment_status") val paymentStatus: String? = null
)

/**
 * Session status response for polling endpoint.
 */
@Serializable
data class SessionResponse(
    @SerialName("session_id")
    val sessionId: String,
    val status: String,               // e.g. "pending", "authenticated", "rejected"
    @SerialName("created_at")
    val createdAt: String = "",
    @SerialName("expires_at")
    val expiresAt: String = ""
)


/**
 * SentinelSeal: what the approver's phone signs. The liveness fields from SentinelHard
 * plus the exact payment being approved. Matches the backend SealPayload schema.
 */
@Serializable
data class SealPayload(
    @SerialName("session_id") val sessionId: String,
    @SerialName("payment_id") val paymentId: String,
    @SerialName("approver_id") val approverId: String,
    val payee: String,
    @SerialName("amount_inr") val amountInr: Double,
    val bpm: Double,
    val timestamp: String,            // ISO-8601 UTC
    @SerialName("device_id") val deviceId: String,
    val snr: Double,
    val variance: Double
)

/** The payment the approver is asked to seal (GET /payments/{id}). */
@Serializable
data class PaymentInfo(
    @SerialName("payment_id") val paymentId: String,
    @SerialName("payee_name") val payeeName: String,
    @SerialName("payee_account_masked") val payeeAccountMasked: String = "",
    @SerialName("amount_inr") val amountInr: Double,
    @SerialName("approver_id") val approverId: String,
    @SerialName("approver_name") val approverName: String = "",
    @SerialName("session_id") val sessionId: String,
    val status: String = ""
)

@Serializable
data class EnrolRequest(
    @SerialName("approver_id") val approverId: String,
    @SerialName("public_key") val publicKey: String,
    @SerialName("attestation_chain") val attestationChain: List<String> = emptyList()
)

@Serializable
data class EnrolResponse(
    @SerialName("approver_id") val approverId: String,
    val name: String = "",
    @SerialName("enrolled_at") val enrolledAt: String = ""
)
