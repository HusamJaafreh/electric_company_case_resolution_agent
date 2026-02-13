#core/serializers.py
from rest_framework import serializers

class CreateCaseRequestSerializer(serializers.Serializer):
    phone = serializers.CharField(required=False, allow_blank=True)
    account_id = serializers.CharField(required=False, allow_blank=True)
    message = serializers.CharField(required=True)
    channel = serializers.ChoiceField(choices=["WEB", "WHATSAPP", "EMAIL"], required=False, default="WEB")


class CreateCaseResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    case_id = serializers.UUIDField(required=False)
    error = serializers.CharField(required=False, allow_blank=True)


class AddMessageRequestSerializer(serializers.Serializer):
    message = serializers.CharField(required=True)
    sender_type = serializers.ChoiceField(choices=["CUSTOMER", "AGENT", "HUMAN"], required=False, default="CUSTOMER")


class AddMessageResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    message_id = serializers.IntegerField(required=False)
    error = serializers.CharField(required=False, allow_blank=True)


class RunCaseAgentResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    result = serializers.DictField(required=False)
    error = serializers.CharField(required=False, allow_blank=True)


class GenerateContentRequestSerializer(serializers.Serializer):
    user_query = serializers.CharField(required=True)


class GenerateContentItemSerializer(serializers.Serializer):
    text = serializers.CharField(required=False, allow_blank=True)
    image = serializers.CharField(required=False, allow_blank=True)


class GenerateContentResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    data = GenerateContentItemSerializer(many=True, required=False)
    message = serializers.CharField(required=False, allow_blank=True)
    error = serializers.CharField(required=False, allow_blank=True)

class CaseInfoSerializer(serializers.Serializer):
    case_id = serializers.UUIDField()
    status = serializers.CharField()
    subject = serializers.CharField()


class CaseMessageOutSerializer(serializers.Serializer):
    message_id = serializers.IntegerField()
    sender_type = serializers.CharField()
    message_text = serializers.CharField()
    created_at = serializers.DateTimeField()


class AgentRunOutSerializer(serializers.Serializer):
    run_id = serializers.IntegerField()
    final_decision = serializers.CharField(allow_null=True, required=False)
    run_status = serializers.CharField()
    started_at = serializers.DateTimeField()
    finished_at = serializers.DateTimeField(allow_null=True, required=False)


class GetCaseResponseSerializer(serializers.Serializer):
    case = CaseInfoSerializer()
    messages = CaseMessageOutSerializer(many=True)
    runs = AgentRunOutSerializer(many=True)


class GetCaseMessagesResponseSerializer(serializers.Serializer):
    messages = CaseMessageOutSerializer(many=True)


# --- Run agent response (structured, but flexible evidence/actions) ---

class RunAgentResultSerializer(serializers.Serializer):
    decision = serializers.CharField()
    reply_text = serializers.CharField()
    case_id = serializers.UUIDField()
    confidence = serializers.FloatField()

    # Keep these generic if you don't want to fully model them yet
    actions = serializers.ListField(child=serializers.DictField(), required=False)
    evidence = serializers.DictField(required=False)
    summary_for_human = serializers.CharField(required=False, allow_blank=True)


class RunCaseAgentResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    result = RunAgentResultSerializer(required=False)
    error = serializers.CharField(required=False, allow_blank=True)