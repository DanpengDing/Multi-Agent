<template>
  <div class="app-wrapper">
    <div class="sidebar">
      <div class="logo">售后多智能体 Knowledge</div>
      <el-menu
        :default-active="activeMenu"
        background-color="#001529"
        text-color="#bfcbd9"
        active-text-color="#409EFF"
        router
        class="el-menu-vertical"
      >
        <el-menu-item index="/knowledge">
          <el-icon><Files /></el-icon>
          <span>知识库管理</span>
        </el-menu-item>
        <el-menu-item index="/chat">
          <el-icon><ChatDotRound /></el-icon>
          <span>智能问答</span>
        </el-menu-item>
      </el-menu>
    </div>
    <div class="main-container">
      <router-view v-slot="{ Component }">
        <transition name="fade-transform" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const activeMenu = computed(() => route.path)
</script>

<style lang="scss" scoped>
.app-wrapper {
  display: flex;
  height: 100vh;
  width: 100%;
  background-color: #0d1117;
  color: #c9d1d9;
}

.sidebar {
  width: 240px;
  background-color: #001529;
  border-right: 1px solid #30363d;
  display: flex;
  flex-direction: column;
  box-shadow: 2px 0 10px rgba(0,0,0,0.5);
  z-index: 10;

  .logo {
    height: 60px;
    line-height: 60px;
    text-align: center;
    font-size: 22px;
    font-weight: bold;
    background: linear-gradient(90deg, #00f260, #0575e6);
    -webkit-background-clip: text;
    color: transparent;
    border-bottom: 1px solid #30363d;
    letter-spacing: 1px;
  }
  
  .el-menu-vertical {
    border-right: none;
  }
}

.main-container {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
  background-image: radial-gradient(#2d333b 1px, transparent 1px);
  background-size: 30px 30px;
  background-color: #0d1117;
}

.fade-transform-leave-active,
.fade-transform-enter-active {
  transition: all 0.4s ease;
}

.fade-transform-enter-from {
  opacity: 0;
  transform: translateX(-20px);
}

.fade-transform-leave-to {
  opacity: 0;
  transform: translateX(20px);
}
</style>
