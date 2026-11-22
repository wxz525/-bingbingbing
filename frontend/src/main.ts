import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import { createApp } from 'vue'

import App from './App.vue'
import './styles/main.css'

createApp(App).use(ElementPlus).mount('#app')
