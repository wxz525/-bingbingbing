<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { CONFLICT_MESSAGE } from '@/api/fundArchive'
import {
  createRuleFormModel,
  RULE_FORM_FIELDS,
  STATUS_OPTIONS,
  type RuleFormModel,
} from '@/constants/redemption'
import type { RedemptionRule, RedemptionRulePayload, SaveErrorState } from '@/types/fundArchive'
import { displayText } from '@/utils/format'
import { buildRulePayload, validateRuleForm } from '@/utils/ruleForm'

const props = defineProps<{
  modelValue: boolean
  fundCode: string
  rule: RedemptionRule | null
  submitting: boolean
  error: SaveErrorState | null
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
  (event: 'submit', payload: RedemptionRulePayload): void
}>()

const form = ref<RuleFormModel>(createRuleFormModel(null))
const clientErrors = ref<Record<string, string>>({})

watch(
  () => props.modelValue,
  (visible) => {
    if (visible) {
      form.value = createRuleFormModel(props.rule)
      clientErrors.value = {}
    }
  },
  { immediate: true },
)

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

const dialogTitle = computed(() => (props.rule ? '编辑申赎要素' : '新增申赎要素'))

const isConflict = computed(
  () => props.error?.status === 409 || props.error?.code === 'VERSION_CONFLICT',
)

const fieldErrors = computed<Record<string, string>>(() => ({
  ...(props.error?.fieldErrors ?? {}),
  ...clientErrors.value,
}))

function handleDateUpdate(value: unknown): void {
  form.value.effective_date = value === null || value === undefined ? '' : String(value)
}

function handleSubmit(): void {
  if (props.submitting) {
    return
  }
  const errors = validateRuleForm(form.value)
  clientErrors.value = errors
  if (Object.keys(errors).length > 0) {
    return
  }
  emit('submit', buildRulePayload(form.value, props.rule))
}
</script>

<template>
  <el-dialog
    v-model="visible"
    :title="dialogTitle"
    width="760px"
    :close-on-click-modal="false"
    data-testid="rule-form-dialog"
  >
    <div class="rule-dialog__subtitle">
      基金代码：<span data-testid="dialog-fund-code">{{ displayText(props.fundCode) }}</span>
    </div>

    <el-alert
      v-if="isConflict"
      class="rule-dialog__alert"
      type="warning"
      :closable="false"
      show-icon
      :title="CONFLICT_MESSAGE"
      data-testid="conflict-alert"
    />
    <el-alert
      v-else-if="props.error"
      class="rule-dialog__alert"
      type="error"
      :closable="false"
      show-icon
      :title="props.error.message"
      data-testid="save-error-alert"
    />

    <el-form label-width="200px" label-position="right" data-testid="rule-form">
      <el-form-item
        v-for="field in RULE_FORM_FIELDS"
        :key="field.key"
        :label="field.label"
        :error="fieldErrors[field.key]"
      >
        <el-select
          v-if="field.control === 'status'"
          v-model="form[field.key]"
          clearable
          placeholder="未提供"
          :data-testid="`field-${field.key}`"
        >
          <el-option
            v-for="option in STATUS_OPTIONS"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>

        <el-date-picker
          v-else-if="field.control === 'date'"
          :model-value="form[field.key] || null"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="YYYY-MM-DD"
          style="width: 100%"
          :data-testid="`field-${field.key}`"
          @update:model-value="handleDateUpdate"
        />

        <el-input
          v-else-if="field.control === 'textarea'"
          v-model="form[field.key]"
          type="textarea"
          :rows="3"
          maxlength="512"
          show-word-limit
          :placeholder="field.placeholder"
          :data-testid="`field-${field.key}`"
        />

        <el-input
          v-else
          v-model="form[field.key]"
          :placeholder="field.placeholder"
          :data-testid="`field-${field.key}`"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button :disabled="props.submitting" @click="visible = false">取消</el-button>
      <el-button
        type="primary"
        :loading="props.submitting"
        :disabled="props.submitting"
        data-testid="submit-rule-button"
        @click="handleSubmit"
      >
        保存
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.rule-dialog__subtitle {
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.rule-dialog__alert {
  margin-bottom: 16px;
}
</style>
